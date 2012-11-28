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


class KanbanBoard:
    data_start_regexp = re.compile('\s*({{{)?#!KanbanBoard')
    data_end_regexp = re.compile('\s*}}}')

    def __init__(self, name, detailed_tickets, env, logger):
        self.name = name
        self.env = env
        self.log = logger
        self.columns = self.load_wiki_data(self.name)['columns']
        self.status_map = self.get_status_to_column_map(self.columns)
        self.tickets = self.fetch_tickets(detailed_tickets)

    # Adds tickets given in "ids" to the board but not necessarily in right column.
    # Always call fix_ticket_columns after this.
    # Returns number of tickets added to the board.
    def add_tickets(self, ids):
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

    # Removes tickets given in "ids" from the board.
    # Returns number of tickets added to the board.
    def remove_tickets(self, ids):
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

    def update_tickets(self):
        self.tickets = self.fetch_tickets([])

    def load_wiki_data(self, page_name):
        self.log.debug('KanbanBoard::load_wiki_data: %s' % page_name)

        page = WikiPage(self.env, page_name)
        if not page.exists:
            self.log.error('Wiki page "%s" doesn\'t exist' % page_name)
            return None

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
            return json.loads('\n'.join(data_lines))

        return None

    def save_wiki_data(self, req):
        self.log.debug('KanbanBoard::save_wiki_data')

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
                    new_lines.append(self.get_json(False))
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
                self.log.debug('TracError: "%s"' % e.message)

    def get_status_to_column_map(self, columns):
        map = {}
        for col in columns:
            for status in col['states']:
                map[status] = col['id']

        return map

    def fetch_tickets(self, detailed):
        self.log.debug('KanbanBoard::fetch_tickets')

        fields = []
        if len(detailed) > 0:
            fields = TicketSystem(self.env).get_ticket_fields()

        tickets = {}
        ids = self.get_ticket_ids()
        for id in ids:
            t = { 'id': id }
            try:
                ticket = model.Ticket(self.env, id)
            except:
                self.log.error('Failed to fetch ticket %d' % id)
                continue

            if id in detailed:
                for field in fields:
                    t[field['name']] = ticket.get_value_or_default(field['name'])

                t['time'] = to_timestamp(ticket['time']) * 1000
                t['changetime'] = to_timestamp(ticket['changetime']) * 1000

                t['changelog'] = []
                changelog = ticket.get_changelog()
                for log_item in changelog:
                    item = {}
                    item['time'] = to_timestamp(log_item[0]) * 1000
                    item['author'] = log_item[1]
                    item['field'] = log_item[2]
                    item['oldValue'] = log_item[3]
                    item['newValue'] = log_item[4]
                    item['permanent'] = log_item[5]
                    t['changelog'].append(item)
            else:
                t['summary'] = ticket.get_value_or_default('summary')
                t['status'] = ticket.get_value_or_default('status')

            tickets[str(id)] = t

        return tickets

    def get_json(self, include_tickets):
        """Return JSON representation of the board.
           If 'includeTickets' is True, each column's 'tickets' property contains ticket objects.
           If False, 'tickets' property is list of ticket IDs.
        """
        result = ''
        if include_tickets:
            jason = { 'columns': [] }
            for col in self.columns:
                colcopy = copy.deepcopy(col)
                colcopy['tickets'] = []
                for t in col['tickets']:
                    try:
                        colcopy['tickets'].append(self.tickets[str(t)])
                    except KeyError:
                        pass
                jason['columns'].append(colcopy)
            result = json.dumps(jason)
        else:
            result = json.dumps({ 'columns': self.columns }, sort_keys=True, indent=2)

        self.log.debug('KanbanBoard::get_json: %s' % result)
        return result

    def get_ticket_ids(self):
        """Return ids of all tickets currently on the board."""
        ids = []
        for col in self.columns:
            ids.extend(col['tickets'])
        return ids

    def update_column(self, new_column):
        self.log.debug('KanbanBoard::update_column: %d' % new_column['id'])
        self.log.debug(new_column)

        if 'tickets' in new_column:
            # convert ticket list to list of integers (ticket IDs)
            new_column['tickets'] = map(lambda x: x['id'], new_column['tickets'])

        for index, column in enumerate(self.columns):
            if column['id'] == new_column['id']:
                for key, value in new_column.items():
                    if key != 'id':
                        self.columns[index][key] = value

    def fix_ticket_columns(self, request, save_changes, force_save):
        """Iterate through all tickets on board and check that ticket state matches column states.
           If it doesn't, move ticket to correct column."""
        self.log.debug('KanbanBoard::fix_ticket_columns')
        modified = False

        ticket_ids = {} # 'columnID': [ticketID, ticketID, ticketID]
        for col in self.columns:
            ticket_ids[str(col['id'])] = []

        for col in self.columns:
            for tid in col['tickets']:
                if (str(tid) in self.tickets):
                    ticket = self.tickets[str(tid)]
                    colId = self.status_map[ticket['status']]
                    if colId != col['id']:
                        modified = True
                        ticket_ids[str(colId)].insert(0, tid)
                    else:
                        ticket_ids[str(colId)].append(tid)

        for col in self.columns:
            col['tickets'] = ticket_ids[str(col['id'])]

        if (modified and save_changes) or force_save:
            self.save_wiki_data(request)

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
      ]
    }
    }}}
    }}}

    Macro accepts following arguments given as 'key=value' pairs right after macro name:
    ||= Key  =||= Description                       =||= Example    =||= Default =||
    || height || Board height in css-accepted format || height=400px || 300px     ||

    Macro name and optional arguments must be followed by board configuration. Configuration is in JSON format and consists of list of columns where each column must have following properties:
    || id || Unique number. ||
    || name || Column name. ||
    || states || List of ticket states which map to this column. For example in example configuration above if the status of ticket #100 changes to "accepted" it moves to middle column (named "Ongoing"). If ticket is dragged to middle column its status changes to first state on this list ("assigned"). ||
    || tickets || List of initial tickets in the column. This list is updated by the macro when ticket status changes. ||
    || wip || Work-in-progress limit for the column. ||
    """

    implements(ITemplateProvider, IRequestHandler)

    request_regexp = re.compile('\/kanbanboard\/(?P<bid>\w+)?')

    # Ticket fields that can should have "not defined" option
    kanban_optional_fields = ['milestone', 'version']

    def save_ticket(self, ticket_data, author, comment=''):
        self.log.debug('KanbanBoardMacro::save_ticket: %d %s' % (ticket_data['id'], author))
        ticket = model.Ticket(self.env, ticket_data['id'])
        for key, value in ticket_data.items():
            if key != 'id':
                ticket[key] = value
        ticket.save_changes(author, comment)

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
    # ?tickets=1,2
    #      Instead of minimal ticket data, returns full data for tickets #1 and #2.
    #
    # ?add=1,2
    #      Before handling request, adds tickets #1 and #2 (if valid) to the board.
    #
    # ?remove=1,2
    #      Before handling request, removes tickets #1 and #2 from the board.

    def process_request(self, req):
        self.log.debug('=== HTTP request: %s, method: %s, user: %s' % (req.path_info, req.method, req.authname))

        if req.method != 'GET' and req.method != 'POST':
            return req.send([], content_type='application/json')

        board_id = None
        match = self.request_regexp.match(req.path_info)
        if match:
            board_id = match.group('bid')

        if board_id is None:
            self.log.debug('=== Get metadata')
            meta_data = {}
            meta_data['ticketFields'] = TicketSystem(self.env).get_ticket_fields()
            for field in meta_data['ticketFields']:
                if field['name'] in self.kanban_optional_fields:
                    field['kanbanOptional'] = True
            return req.send(json.dumps(meta_data), content_type='application/json')

        arg_list = parse_arg_list(req.query_string)
        detailed_tickets = []
        added_tickets = []
        removed_tickets= []
        for arg in arg_list:
            if arg[0] == 'tickets':
                detailed_tickets = self._parse_id_list(arg[1])
            elif arg[0] == 'add':
                added_tickets = self._parse_id_list(arg[1])
            elif arg[0] == 'remove':
                removed_tickets = self._parse_id_list(arg[1])
        self.log.debug('Detailed tickets: %s' % repr(detailed_tickets))
        self.log.debug('Added tickets: %s' % repr(added_tickets))
        self.log.debug('Removed tickets: %s' % repr(removed_tickets))

        board = KanbanBoard(board_id, detailed_tickets, self.env, self.log)

        added = 0
        if len(added_tickets) > 0:
            added = board.add_tickets(added_tickets)

        removed = 0
        if len(removed_tickets) > 0:
            removed = board.remove_tickets(removed_tickets)

        # We need to update board data to match (possibly changed) ticket states
        is_editable = 'WIKI_MODIFY' in req.perm and 'TICKET_MODIFY' in req.perm
        self.log.debug('is_editable: %s', is_editable)
        board.fix_ticket_columns(req, is_editable, added > 0 or removed > 0)

        if req.method == 'GET':
            self.log.debug('=== Get all columns')
            return req.send(board.get_json(True), content_type='application/json')
        else:
            self.log.debug('=== Update columns (and tickets)')
            columnData = json.loads(req.read())
            for col in columnData:
                for ticket in col['tickets']:
                    for key, value in ticket.items():
                        if key != 'id':
                            self.save_ticket(ticket, req.authname)
                            break

                board.update_column(col)

            board.update_tickets()
            board.fix_ticket_columns(req, True, True)
            return req.send(board.get_json(True), content_type='application/json')

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('trackanbanboard', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('kbm', os.path.abspath(resource_filename('trackanbanboard', 'htdocs')))]

    def expand_macro(self, formatter, name, text, args):
        if text is None:
            data = {
                'error': 'Board data is not defined',
                'usage': format_to_html(self.env, formatter.context, self.__doc__)
            }
            add_stylesheet(formatter.req, 'kbm/css/kanbanboard.css')
            return Chrome(self.env).render_template(formatter.req,
                'kanbanerror.html',
                data,
                None,
                fragment=True).render(strip_whitespace=False)

        self.log.debug(args)
        board_height = '300px'
        if args:
            board_height = args.get('height', '300px')

        project_name = self.env.path.split('/')[-1]
        page_name = formatter.req.path_info.split('/')[-1]
        is_editable = 'WIKI_MODIFY' in formatter.req.perm and 'TICKET_MODIFY' in formatter.req.perm

        data = {
            'css_class': 'trac-kanban-board-macro',
            'height': board_height
        }
        jsGlobals = {
            'KANBAN_BOARD_ID': page_name,
            'TRAC_PROJECT_NAME': project_name,
            'IS_EDITABLE': is_editable
        }

        add_script(formatter.req, 'kbm/js/libs/jquery-1.8.2.js')
        add_script(formatter.req, 'kbm/js/libs/jquery-ui-1.9.1.custom.min.js')
        add_script(formatter.req, 'kbm/js/libs/knockout-2.2.0.js')
        add_script(formatter.req, 'kbm/js/libs/knockout.mapping.js')
        add_script(formatter.req, 'kbm/js/libs/knockout-sortable.min.js')
        add_script(formatter.req, 'kbm/js/kanbanutil.js')
        add_script(formatter.req, 'kbm/js/kanbanboard.js')
        add_script_data(formatter.req, jsGlobals)
        add_stylesheet(formatter.req, 'kbm/css/jquery-ui-1.9.1.custom.min.css')
        add_stylesheet(formatter.req, 'kbm/css/kanbanboard.css')

        return Chrome(self.env).render_template(formatter.req,
            'kanbanboard.html',
            data,
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
