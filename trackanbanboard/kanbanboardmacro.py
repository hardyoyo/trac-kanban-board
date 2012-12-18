import copy
import json
import os.path
import re

import trac.ticket.model as model

from trac.core import implements, TracError
from trac.ticket.api import TicketSystem
from trac.util.datefmt import to_timestamp
from trac.web import IRequestHandler
from trac.web.api import parse_arg_list
from trac.web.chrome import ITemplateProvider, Chrome, add_stylesheet, add_script, add_script_data
from trac.wiki.formatter import format_to_html
from trac.wiki.macros import WikiMacroBase
from trac.wiki.model import WikiPage


class KanbanError(Exception):
    """Base class for all Kanban board exceptions."""
    pass


class InvalidDataError(KanbanError):
    """Raised when board data can not be found or parsed."""
    def __init__(self, msg):
        self.msg = msg


class InvalidFieldError(KanbanError):
    """Raised when invalid ticket field definition is detected."""
    def __init__(self, fields):
        self.fields = fields


class KanbanBoard:
    data_start_regexp = re.compile('\s*({{{)?#!KanbanBoard')
    data_end_regexp = re.compile('\s*}}}')

    # These are ticket fields that must be present on all tickets
    mandatory_fields = ['summary', 'status']

    # These ticket fields are shown in detail dialog regardless of user's field definitions
    always_shown_fields = ['summary', 'description', 'time', 'changetime']

    def __init__(self, name, detailed_tickets, ticket_fields, env, logger):
        self.name = name
        self.env = env
        self.log = logger

        # List of valid ticket fields and options as returned by TicketSystem.get_ticket_fields()
        self.ticket_fields = ticket_fields

        data = self.load_wiki_data(self.name)
        if 'fields' in data:
            invalid_fields = self.get_invalid_fields(data['fields'], self.ticket_fields)
            if invalid_fields:
                raise InvalidFieldError(invalid_fields)
            self.fields = []
            for field_name in data['fields']:
                if field_name not in self.always_shown_fields:
                    self.fields.append(field_name)
        else:
            self.fields = []

        if 'columns' in data and data['columns']:
            self.columns = data['columns']
        else:
            raise InvalidDataError('No columns defined')

        # Map of ticket status names to matching column IDs
        self.status_map = self.get_status_to_column_map(self.columns)

        self.tickets = {}
        self.fetch_tickets(self.tickets, self.get_ticket_ids(), detailed_tickets)

    def add_tickets(self, ids):
        """Add tickets given in "ids" to the board but not necessarily in right column.
           Always call fix_ticket_columns after this.
           Returns number of tickets added to the board.
        """
        if not self.columns:
            return 0

        current_ids = self.get_ticket_ids()
        valid_ids = []
        for id in ids:
            if id in current_ids:
                self.log.error('Ticket %d is already on the board' % id)
                continue

            t = { 'id': id }
            try:
                ticket = model.Ticket(self.env, id)
            except:
                self.log.error('Failed to fetch ticket %d' % id)
                continue

            t['summary'] = ticket.get_value_or_default('summary')
            t['status'] = ticket.get_value_or_default('status')
            self.tickets[str(id)] = t
            valid_ids.append(id)

        self.columns[0]['tickets'].extend(valid_ids)
        return len(valid_ids)

    def remove_tickets(self, ids):
        """Remove tickets given in "ids" from the board.
           Returns number of tickets removed from the board.
        """
        if not self.columns:
            return 0

        removed = 0
        for col in self.columns:
            new_list = []
            for tid in col['tickets']:
                if tid in ids:
                    try:
                        del self.tickets[str(tid)]
                        removed += 1
                    except KeyError:
                        pass
                else:
                    new_list.append(tid)
            col['tickets'] = new_list

        return removed

    def update_tickets(self, ids):
        if ids:
            self.fetch_tickets(self.tickets, ids, [])
        else:
            self.fetch_tickets(self.tickets, self.get_ticket_ids(), [])

    def load_wiki_data(self, page_name):
        page = WikiPage(self.env, page_name)
        if not page.exists:
            self.log.error('Wiki page "%s" doesn\'t exist' % page_name)
            raise InvalidDataError('Wiki page doesn\'t exist')

        lines = page.text.split('\n')
        first = -1
        last = -1
        data_lines = []

        for index, line in enumerate(lines):
            if first < 0:
                if self.data_start_regexp.match(line):
                    first = index + 1
            else:
                if self.data_end_regexp.match(line):
                    last = index - 1
                elif last < 0:
                    data_lines.append(line)

        if last > 0:
            if data_lines:
                try:
                    return json.loads('\n'.join(data_lines))
                except ValueError:
                    raise InvalidDataError('Invalid JSON data')
            else:
                raise InvalidDataError('Empty data')

        if first < 0:
            raise InvalidDataError('First line of data not found')

        raise InvalidDataError('Last line of data not found')

    def save_wiki_data(self, req):
        page = WikiPage(self.env, self.name)
        if not page.exists:
            self.log.error('Wiki page "%s" doesn\'t exist' % self.name)
            return None

        lines = page.text.split('\n')
        first = -1
        last = -1
        new_lines = []

        for index, line in enumerate(lines):
            if first < 0:
                new_lines.append(line)
                if self.data_start_regexp.match(line):
                    first = index + 1
                    new_lines.append(self.get_json(False, True))
            elif last < 0:
                if self.data_end_regexp.match(line):
                    last = index - 1
                    new_lines.append(line)
            else:
                new_lines.append(line)

        if last > 0:
            page.text = '\n'.join(new_lines)
            try:
                page.save(req.authname, 'Kanban board data changed', req.remote_addr)
            except TracError as e:
                self.log.error('TracError: "%s"' % e.message)

    def get_status_to_column_map(self, columns):
        map = {}
        for col in columns:
            for status in col['states']:
                map[status] = col['id']

        return map

    def fetch_tickets(self, tickets, ids, detailed):
        for id in ids:
            t = { 'id': id }
            try:
                ticket = model.Ticket(self.env, id)
            except:
                self.log.error('Failed to fetch ticket %d' % id)
                if str(id) in tickets:
                    delattr(tickets, str(id))
                continue

            # Get mandatory fields
            for field_name in self.mandatory_fields:
                t[field_name] = ticket.get_value_or_default(field_name)

            if id in detailed:
                # Get fields that are are always shown in detail dialog
                for field_name in self.always_shown_fields:
                    if field_name not in t:
                        t[field_name] = ticket.get_value_or_default(field_name)

                # Get user specified extra fields
                for field_name in self.fields:
                    if field_name not in self.mandatory_fields:
                        t[field_name] = ticket.get_value_or_default(field_name)

                # Convert DateTimes to (millisecond) timestamps
                if 'time' in t:
                    t['time'] = to_timestamp(t['time']) * 1000
                if 'changetime' in t:
                    t['changetime'] = to_timestamp(t['changetime']) * 1000

                # Get changes and comments and group changes from same action together
                t['changelog'] = []
                changelog = ticket.get_changelog()
                time_entry = None
                for log_item in changelog:
                    current_time = to_timestamp(log_item[0]) * 1000
                    if time_entry is None or time_entry['time'] < current_time:
                        if time_entry is not None:
                            t['changelog'].append(time_entry)
                        time_entry = {}
                        time_entry['time'] = current_time
                        time_entry['author'] = log_item[1]
                        time_entry['changes'] = []

                    change_entry = {}
                    change_entry['field'] = log_item[2]
                    change_entry['oldValue'] = log_item[3]
                    change_entry['newValue'] = log_item[4]
                    time_entry['changes'].append(change_entry)

                if time_entry is not None:
                    t['changelog'].append(time_entry)

            tickets[str(id)] = t

    def get_json(self, include_tickets, include_fields):
        """Return JSON representation of the board.
           If 'includeTickets' is True, each column's 'tickets' property contains ticket objects.
           If False, 'tickets' property is list of ticket IDs.
        """
        result = ''
        jason = {}
        indent = None
        if include_fields and self.fields:
            jason['fields'] = self.fields
        if include_tickets:
            jason['columns'] = []
            for col in self.columns:
                colcopy = copy.deepcopy(col)
                colcopy['tickets'] = []
                for t in col['tickets']:
                    try:
                        colcopy['tickets'].append(self.tickets[str(t)])
                    except KeyError:
                        pass
                jason['columns'].append(colcopy)
        else:
            jason['columns'] = self.columns
            indent = 2

        result = json.dumps(jason, sort_keys=(indent is not None), indent=indent)
        return result

    def get_ticket_ids(self):
        """Return ids of all tickets currently on the board."""
        ids = []
        for col in self.columns:
            ids.extend(col['tickets'])
        return ids

    def update_column(self, new_column):
        if 'tickets' in new_column:
            # convert ticket list to list of integers (ticket IDs)
            new_column['tickets'] = map(lambda x: x['id'], new_column['tickets'])

        for index, column in enumerate(self.columns):
            if column['id'] == new_column['id']:
                for key, value in new_column.items():
                    if key == 'tickets':
                        self.columns[index]['tickets'] = self.merge_ticket_lists(
                                self.columns[index]['tickets'], new_column['tickets'])
                    elif key != 'id':
                        self.columns[index][key] = value

    def merge_ticket_lists(self, original, new):
        """Merge two lists so that result has all items from original list in order that matches
           new list as closely as possible. Example: original [1,2,3,4,5], new [1,4,2,5], result
           [1,4,2,3,5] (4 moved in front of 2, 3 added)
        """
        if len(original) >= len(new):
            """Go through all items in original list:
                - If item is not in new list (i.e. it is added), append it to result list
                - If item is already in result list, skip it
                - Else, append all items from start of new list up to the original list item
                  (that are not already in result list) to result list
            """
            merged = []
            for ot in original:
                if ot in merged:
                    continue
                if ot in new:
                    for nt in new:
                        if nt is not ot:
                            if nt not in merged:
                                merged.append(nt)
                        else:
                            merged.append(nt)
                            break
                else:
                    merged.append(ot)
            return merged
        else:
            return new

    def fix_ticket_columns(self, request, save_changes, force_save):
        """Iterate through all tickets on board and check that ticket state matches column states.
           If it doesn't, move ticket to correct column. Invalid tickets and duplicates are removed
           in the process.
        """
        modified = False

        old_lists = {} # key: column ID (as string), value: list of ticket IDs (integers)
        new_lists = {} #
        for col in self.columns:
            old_lists[str(col['id'])] = col['tickets']
            new_lists[str(col['id'])] = []

        for col in self.columns:
            for tid in col['tickets']:
                if (str(tid) in self.tickets):
                    ticket = self.tickets[str(tid)]
                    target_col = self.status_map[ticket['status']]
                    if target_col != col['id']:
                        if tid not in old_lists[str(target_col)]:
                            modified = True
                            new_lists[str(target_col)].insert(0, tid)
                    else:
                        new_lists[str(target_col)].append(tid)

        for col in self.columns:
            col['tickets'] = new_lists[str(col['id'])]

        if (modified and save_changes) or force_save:
            self.save_wiki_data(request)

    def get_field_string(self):
        if self.fields:
            return ','.join(self.fields)
        return ''

    def get_invalid_fields(self, fields, valid_fields):
        valid_names = map(lambda x: x['name'], valid_fields)
        invalid_fields = []
        for field_name in fields:
            if field_name not in valid_names:
                invalid_fields.append(field_name)
        return invalid_fields

class KanbanBoardMacro(WikiMacroBase):
    """
    Usage:

    {{{
    {{{
    #!KanbanBoard height=400px
    {
      "columns": [
        { "id": 1, "name": "New", "states": ["new"], "tickets": [100, 124, 103], "wip": 5 },
        { "id": 2, "name": "Ongoing", "states": ["assigned", "accepted", "reopened"], "tickets": [], "wip": 3 },
        { "id": 3, "name": "Done", "states": ["closed"], "tickets": [], "wip": 5 }
      ],
      "fields": [
        "status", "priority", "keywords"
      ]
    }
    }}}
    }}}

    Macro accepts following arguments given as 'key=value' pairs right after macro name:
    ||= Key  =||= Description                       =||= Example    =||= Default =||
    || height || Board height in css-accepted format || height=400px || 300px     ||

    Macro name and optional arguments must be followed by board configuration. Configuration
    is in JSON format and consists of list of columns and optionally list of ticket fields.
    Each column must have following properties:
    || id || Unique number ||
    || name || Column name ||
    || states || List of ticket states which map to this column. For example in example \
    configuration above if the status of ticket #100 changes to "accepted" it moves to \
    middle column (named "Ongoing"). If ticket is dragged to middle column its status \
    changes to first state on this list ("assigned"). ||
    || tickets || List of initial tickets in the column. This list is updated by the \
    macro when ticket status changes ||
    || wip || Work-in-progress limit for the column ||

    The "fields" property defines which ticket fields are shown on the ticket detail dialog.
    Valid field names on default Trac environment are: "reporter", "owner", "status",
    "type", "priority", "milestone", "component", "version", "resolution", "keywords" and "cc".
    """

    implements(ITemplateProvider, IRequestHandler)

    request_regexp = re.compile('\/kanbanboard\/((?P<bid>\w+)(?P<ticket>\/ticket)?)?')

    ticket_fields = []

    def save_ticket(self, ticket_data, author):
        """If ticket_data contains an ID, modifies defined fields in that ticket.
           If not, creates new ticket. Returns the ID of new/modified ticket."""

        id = None
        comment = ''

        if 'id' in ticket_data:
            id = ticket_data['id']
        ticket = model.Ticket(self.env, id)

        for key, value in ticket_data.items():
            if key == 'comment':
                comment = value
            elif key != 'id':
                ticket[key] = value
        if id:
            ticket.save_changes(author, comment)
        else:
            ticket.insert()
            id = ticket.id

        return id

    def match_request(self, req):
        return self.request_regexp.match(req.path_info)

    # GET  /kanbanboard/
    #      Returns metadata (ticket fields etc.)
    #
    # GET  /kanbanboard/[board ID]
    #      Returns board data including minimal ticket data for all tickets on the board.
    #
    # POST /kanbanboard/[board ID]
    #      Updates board data and saves ticket changes. Returns board & ticket data.
    #
    # POST /kanbanboard/[board ID]/ticket
    #      Gets ticket data as input. If data contains ticket ID, modifies that ticket.
    #      If not, creates new ticket and adds it to the board. Returns board & ticket data.
    #
    # ?detailed=1,2
    #      Instead of minimal ticket data, returns full data for tickets #1 and #2.
    #
    # ?add=1,2
    #      Before handling request, adds tickets #1 and #2 (if valid) to the board.
    #
    # ?remove=1,2
    #      Before handling request, removes tickets #1 and #2 from the board.

    def process_request(self, req):
        self.log.debug('HTTP request: %s, method: %s, user: %s' % (req.path_info, req.method, req.authname))

        if req.method != 'GET' and req.method != 'POST':
            return req.send([], content_type='application/json')

        board_id = None
        is_ticket_call = False
        match = self.request_regexp.match(req.path_info)
        if match:
            board_id = match.group('bid')
            is_ticket_call = match.group('ticket') is not None

        if not self.ticket_fields:
            self.ticket_fields = TicketSystem(self.env).get_ticket_fields()

        if board_id is None:
            meta_data = {}
            meta_data['ticketFields'] = self.ticket_fields
            return req.send(json.dumps(meta_data), content_type='application/json')

        arg_list = parse_arg_list(req.query_string)
        detailed_tickets = []
        added_tickets = []
        removed_tickets= []
        for arg in arg_list:
            if arg[0] == 'detailed':
                detailed_tickets = self._parse_id_list(arg[1])
            elif arg[0] == 'add':
                added_tickets = self._parse_id_list(arg[1])
            elif arg[0] == 'remove':
                removed_tickets = self._parse_id_list(arg[1])

        board = KanbanBoard(board_id, detailed_tickets, self.ticket_fields, self.env, self.log)

        added = 0
        if len(added_tickets) > 0:
            added = board.add_tickets(added_tickets)

        removed = 0
        if len(removed_tickets) > 0:
            removed = board.remove_tickets(removed_tickets)

        # We need to update board data to match (possibly changed) ticket states
        is_editable = 'WIKI_MODIFY' in req.perm and 'TICKET_MODIFY' in req.perm
        board.fix_ticket_columns(req, is_editable, added > 0 or removed > 0)

        if req.method == 'GET':
            return req.send(board.get_json(True, False), content_type='application/json')
        else:
            if is_ticket_call:
                ticket_data = json.loads(req.read())
                is_new = 'id' not in ticket_data
                id = self.save_ticket(ticket_data, req.authname)
                if is_new:
                    board.add_tickets([id])
                else:
                    board.update_tickets([id])
            else:
                modified_tickets = []
                columnData = json.loads(req.read())
                for col in columnData:
                    for ticket in col['tickets']:
                        for key, value in ticket.items():
                            if key != 'id':
                                self.save_ticket(ticket, req.authname)
                                modified_tickets.append(ticket['id'])
                                break

                    board.update_column(col)
                if modified_tickets:
                    board.update_tickets(modified_tickets)

            board.fix_ticket_columns(req, True, True)
            return req.send(board.get_json(True, False), content_type='application/json')

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('trackanbanboard', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('trackanbanboard', os.path.abspath(resource_filename('trackanbanboard', 'htdocs')))]

    def expand_macro(self, formatter, name, text, args):
        template_data = {'css_class': 'trac-kanban-board'}
        template_file = 'kanbanboard.html'
        board = None

        template_data['height'] = '300px'
        if args:
            template_data['height'] = args.get('height', '300px')

        project_name = self.env.path.split('/')[-1]
        page_name = formatter.req.path_info.split('/')[-1]
        is_editable = 'WIKI_MODIFY' in formatter.req.perm and 'TICKET_MODIFY' in formatter.req.perm

        js_globals = {
            'KANBAN_BOARD_ID': page_name,
            'TRAC_PROJECT_NAME': project_name,
            'TRAC_USER_NAME': formatter.req.authname,
            'IS_EDITABLE': is_editable
        }

        if not self.ticket_fields:
            self.ticket_fields = TicketSystem(self.env).get_ticket_fields()

        if text is None:
            template_data['error'] = 'Board data is not defined'
            template_data['usage'] = format_to_html(self.env, formatter.context, self.__doc__)
        else:
            try:
                board = KanbanBoard(page_name, [], self.ticket_fields, self.env, self.log)
            except InvalidDataError as e:
                template_data['error'] = e.msg
                template_data['usage'] = format_to_html(self.env, formatter.context, self.__doc__)
            except InvalidFieldError as e:
                template_data['error'] = 'Invalid ticket fields: %s' % ', '.join(e.fields)
                valid_fields = map(lambda x: x['name'], self.ticket_fields)
                template_data['usage'] = 'Valid field names are: %s.' % ', '.join(valid_fields)

        if board:
            # TICKET_FIELDS is comma-separated list of user defined ticket field names
            js_globals['TICKET_FIELDS'] = board.get_field_string()

        add_stylesheet(formatter.req, 'trackanbanboard/css/kanbanboard.css')
        add_script_data(formatter.req, js_globals)

        if 'error' in template_data:
            template_file = 'kanbanerror.html'
        else:
            add_script(formatter.req, 'trackanbanboard/js/libs/jquery-1.8.3.js')
            add_script(formatter.req, 'trackanbanboard/js/libs/jquery-ui-1.9.2.custom.min.js')
            add_script(formatter.req, 'trackanbanboard/js/libs/knockout-2.2.0.js')
            add_script(formatter.req, 'trackanbanboard/js/libs/knockout.mapping.js')
            add_script(formatter.req, 'trackanbanboard/js/libs/knockout-sortable.min.js')
            add_script(formatter.req, 'trackanbanboard/js/kanbanutil.js')
            add_script(formatter.req, 'trackanbanboard/js/kanbanboard.js')
            add_stylesheet(formatter.req, 'trackanbanboard/css/jquery-ui-1.9.2.custom.min.css')

        return Chrome(self.env).render_template(formatter.req,
            template_file,
            template_data,
            None,
            fragment=True).render(strip_whitespace=False)

    # In: comma-separated list of integers (as string)
    # Out: list of integers
    def _parse_id_list(self, ids):
        result = []
        parts = ids.split(',')
        for part in parts:
            try:
                result.append(int(part))
            except ValueError:
                pass
        return result

