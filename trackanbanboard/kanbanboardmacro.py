import copy
import json
import os.path
import re
import time

import trac.ticket.model as model

from trac.core import implements, TracError
from trac.ticket.query import Query
from trac.wiki.api import parse_args
from trac.wiki.macros import WikiMacroBase
from trac.web import IRequestHandler
from trac.web.chrome import ITemplateProvider, Chrome, add_stylesheet, add_script, add_script_data
from trac.wiki.model import WikiPage

REQ_REGEXP = re.compile('\/kanbanboard\/(?P<bid>\w+)')

class KanbanBoard:
    dataStartRe = re.compile('(?P<start><(textarea|TEXTAREA)[^>]+(id|ID)=["\']kanbanBoardData["\'][^>]*>)')
    dataEndRe = re.compile('(<\/(textarea|TEXTAREA)>)')
    dataStartTag = '<textarea id="kanbanBoardData">'
    dataEndTag = '</textarea>'

    def __init__(self, name, request, env, logger):
        self.name = name
        self.env = env
        self.log = logger
        self.columns = self.load_wiki_data(self.name)
        self.statusMap = self.get_status_to_column_map(self.columns)
        self.tickets = self.fetch_tickets(request)

    def is_ready(self):
        return self.columns is not None

    def load_wiki_data(self, pageName):
        self.log.debug('KanbanBoard::load_wiki_data: %s' % pageName)

        page = WikiPage(self.env, pageName)
        if not page.exists:
            self.log.error('Wiki page "%s" doesn\'t exist' % pageName)
            return None

        lines = page.text.split('\n')
        first = -1
        last = -1
        dataLines = []

        for index, line in enumerate(lines):
            if first < 0:
                if self.dataStartRe.match(line):
                    first = index + 1
            else:
                if self.dataEndRe.match(line):
                    last = index - 1
                elif last < 0:
                    dataLines.append(line)

        if last > 0:
            return json.loads('\n'.join(dataLines))

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
        newLines = []

        for index, line in enumerate(lines):
            if first < 0:
                newLines.append(line)
                if self.dataStartRe.match(line):
                    first = index + 1
                    newLines.append(self.get_json(False))
            elif last < 0:
                if self.dataEndRe.match(line):
                    last = index - 1
                    newLines.append(line)
            else:
                newLines.append(line)

        if last > 0:
            page.text = '\n'.join(newLines)
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

    def fetch_tickets(self, req):
        self.log.debug('KanbanBoard::fetch_tickets')
        queryString = self.get_ticket_query_string()
        self.log.debug('query string: %s' % queryString)
        if queryString == "":
            return []

        query = Query.from_string(self.env, queryString)
        ticketList = query.execute(req)
        tickets = {}

        # convert times to epoch timestamps
        for t in ticketList:
            idStr = str(t['id'])
            tickets[idStr] = t
            tickets[idStr]['time'] = int(time.mktime(t['time'].timetuple()))
            tickets[idStr]['changetime'] = int(time.mktime(t['changetime'].timetuple()))

        return tickets

    def get_json(self, includeTickets):
        """Return JSON representation of the board."""
        result = ''
        if includeTickets:
            jason = []
            for col in self.columns:
                colcopy = copy.deepcopy(col)
                colcopy['tickets'] = []
                for t in col['tickets']:
                    try:
                        colcopy['tickets'].append(self.tickets[str(t)])
                    except KeyError:
                        pass
                jason.append(colcopy)
            result = json.dumps(jason)
        else:
            result = json.dumps(self.columns, sort_keys=True, indent=2)

        self.log.debug('KanbanBoard::get_json: %s' % result)
        return result

    def get_ticket_query_string(self):
        """Return Trac query string which can be used to fetch all tickets on the board."""
        ids = self.get_ticket_ids()
        queryString = '&'.join(('id=' + str(x)) for x in ids)
        return queryString

    def get_ticket_ids(self):
        """Return ids of all tickets currently on the board."""
        ids = []
        for col in self.columns:
            ids.extend(col['tickets'])
        return ids

    def update_column(self, newColumn):
        self.log.debug('KanbanBoard::update_column: %d' % newColumn['id'])
        self.log.debug(newColumn)
        for index, column in enumerate(self.columns):
            if column['id'] == newColumn['id']:
                self.columns[index] = newColumn
                # convert ticket list to list of integers (ticket IDs)
                self.columns[index]['tickets'] = map(lambda x: x['id'], newColumn['tickets'])

    def fix_ticket_columns(self, request, saveChanges):
        """Iterate through all tickets on board and check that ticket state matches column states.
           If it doesn't, move ticket to correct column."""
        self.log.debug('KanbanBoard::fix_ticket_columns')
        modified = False

        ticketIds = {}
        for col in self.columns:
            ticketIds[str(col['id'])] = []

        for col in self.columns:
            for tid in col['tickets']:
                if (str(tid) in self.tickets):
                    ticket = self.tickets[str(tid)]
                    colId = self.statusMap[ticket['status']]
                    if colId is not col['id']:
                        modified = True
                        ticketIds[str(colId)].insert(0, tid)
                    else:
                        ticketIds[str(colId)].append(tid)

        for col in self.columns:
            col['tickets'] = ticketIds[str(col['id'])]

        if modified and saveChanges:
            self.save_wiki_data(request)

class KanbanBoardMacro(WikiMacroBase):
    """Insert simple kanban board into the wiki page.

    Macro accepts following arguments as comma separated list of 'key=value' pairs:
    ||= Key  =||= Description                       =||= Example    =||
    || height || Board height in css-accepted format || height=300px ||

    Board configuration and data is stored on separate textarea on same wiki page as the macro. Below is an example configuration:

    {{{
    {{{
        #!html
        <textarea id="kanbanBoardData" style="display: none;">
        [
            { "id": 1, "name": "New", "states": ["new"], "tickets": [100, 124, 103], "wip": 5 },
            { "id": 2, "name": "Ongoing", "states": ["assigned, accepted, reopened"], "tickets": [], "wip": 3 },
            { "id": 3, "name": "Done", "states": ["closed"], "tickets": [], "wip": 5 }
        ]
        </textarea>
    }}}
    }}}

    Configuration must be inside textarea tags with id attribute "kanbanBoardData". Opening and closing tags must be on their own lines.
    The configuration itself is in JSON format and consists of list of column objects. Each column must have following properties:
    || id || Unique number. ||
    || name || Column name. ||
    || states || List of ticket states which map to this column. For example in example configuration above if the status of ticket #100 changes to "accepted" it moves to middle column (named "Ongoing"). If ticket is dragged to middle column its status changes to first state on this list ("assigned"). ||
    || tickets || List of initial tickets (ticket IDs) in the column. This list is updated by the macro when ticket status changes. ||
    || wip || Work-in-progress limit for the column. ||
    """

    implements(ITemplateProvider, IRequestHandler)

    def save_ticket(self, ticketData, author, comment=''):
        self.log.debug('KanbanBoardMacro::save_ticket: %d %s' % (ticketData['id'], author))
        ticket = model.Ticket(self.env, ticketData['id'])
        if ticket['status'] is not ticketData['status']:
            ticket['status'] = ticketData['status']
        ticket.save_changes(author, comment)

    def match_request(self, req):
        return REQ_REGEXP.match(req.path_info)

    # GET  /kanbanboard/[board ID]/ returns board data
    # POST /kanbanboard/[board ID]/ updates board data and saves ticket changes
    def process_request(self, req):
        self.log.debug('=== HTTP request: %s, method: %s, user: %s' % (req.path_info, req.method, req.authname))

        if req.method != 'GET' and req.method != 'POST':
            return req.send([], content_type='application/json')

        boardId = 0
        match = REQ_REGEXP.match(req.path_info)
        if match:
            boardId = match.group('bid')

        if boardId == 0:
            return req.send([], content_type='application/json')

        board = KanbanBoard(boardId, req, self.env, self.log)

        # We need to update board data to match (possibly changed) ticket states
        isEditable = 'WIKI_MODIFY' in req.perm and 'TICKET_MODIFY' in req.perm
        self.log.debug('isEditable: %s', isEditable)
        board.fix_ticket_columns(req, isEditable)

        if req.method == 'GET':
            self.log.debug('=== Get all columns')
            return req.send(board.get_json(True), content_type='application/json')
        else:
            self.log.debug('=== Update columns (and tickets)')
            columnData = json.loads(req.read())
            for col in columnData:
                for ticket in col['tickets']:
                    if 'status' in ticket:
                        self.save_ticket(ticket, req.authname)

                board.update_column(col)
            board.save_wiki_data(req)
            return req.send([], content_type='application/json')

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('trackanbanboard', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('kbm', os.path.abspath(resource_filename('trackanbanboard', 'htdocs')))]

    def expand_macro(self, formatter, name, text):
        args = parse_args(text)
        self.log.debug(args)
        boardHeight = '300px'
        if args:
            boardHeight = args[1].get('height', '300px')

        projectName = self.env.path.split('/')[-1]
        pageName = formatter.req.path_info.split('/')[-1]
        isEditable = 'WIKI_MODIFY' in formatter.req.perm and 'TICKET_MODIFY' in formatter.req.perm

        data = {
            'css_class': 'trac-kanban-board-macro',
            'height': boardHeight
        }
        jsGlobals = {
            'KANBAN_BOARD_ID': pageName,
            'TRAC_PROJECT_NAME': projectName,
            'IS_EDITABLE': isEditable
        }

        add_script(formatter.req, 'kbm/js/libs/jquery-ui-1.9.1.custom.min.js')
        add_script(formatter.req, 'kbm/js/libs/knockout-2.2.0.js')
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
