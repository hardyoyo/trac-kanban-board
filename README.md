Trac Kanban Board
=================

TracKanbanBoard is a Trac wiki macro for managing tickets with agile Kanban
method. Add KanbanBoard macro to wiki page and use it to prioritize and manage
tickets in the project.

Main features:

* Define board columns and how they map to ticket states
* Change ticket state by dragging tickets on the board
* Add existing tickets to board by drag-and-dropping ticket links
* Create new tickets directly from board
* View and modify ticket fields (summary, description, etc.) and add comments
  from ticket detail dialog
* Define what ticket fields are visible on ticket detail dialog

See also
[Trac MultiProject Plug-in](https://github.com/nokia-developer/trac-multiproject).


Installation
-------------------------------------------------------------------------------

1. Clone the repository:

```
    $ git clone https://github.com/nokia-developer/trac-kanban-board.git trackanbanboard
```

2. Run the setup script:

```
    $ cd trackanbanboard
    $ python setup.py install
```

3. Enable component in Trac configuration:

```
    [components]
    trackanbanboard.* = enabled
```

4. Create/modify wiki page and put `KanbanBoard` processor in it. Empty data
   will give an error but also the detailed usage instructions:

```
    This is wiki text:
    {{{
    #!KanbanBoard
    }}}
```


Data storage
-------------------------------------------------------------------------------

Plug-in uses Trac tickets as kanban board "cards". Any existing ticket from
project can be added to the board and modified either from board or from default
Trac ticket view.

Board configuration and state is stored on wiki page inside `KanbanBoard`
processor block in JSON format (see example below). When cards are moved around,
plug-in updates the state and rewrites the wiki page.

Below is an example macro definition that produces kanban board with three
columns (New, Ongoing and Done) and shows status and priority fields in ticket
dialog. First column contains three tickets (in order from top to bottom: \#23,
\#24 and \#25), second column one ticket and third column is empty. Invalid ticket
IDs in configuration are ignored and removed automatically when board state is
saved.

```
    #!KanbanBoard height=250px
    {
      "columns": [
        { "id": 1, "name": "New", "states": ["new"], "tickets": [23, 24, 25], "wip": 3 },
        { "id": 2, "name": "Ongoing", "states": ["assigned", "accepted", "reopened"], "tickets": [21], "wip": 3 },
        { "id": 3, "name": "Done", "states": ["closed"], "tickets": [], "wip": 5 }
      ],
      "fields": [
        "status", "priority"
      ]
    }
```

Description for different options and properties can be displayed with
`[[MacroList(KanbanBoard)]]` macro.


How to use
-------------------------------------------------------------------------------

Tickets can be added to board by drag-and-dropping ticket links to board. Links
can be dragged from same page as board, separate browser window or from the
ticket query dialog which can be opened by clicking the 'Add tickets' button.

New ticket can be created by clicking the 'New ticket' button and entering
ticket details. Tickets created this way are added to board automatically.

Each "card" on board displays ticket ID and summary. Additional details can be
viewed in ticket detail dialog which can be opened by clicking individual cards.
Detail dialog contains:

* Link to corresponding Trac ticket page (in title bar)
* Ticket creation and modification times
* Summary
* Any user defined fields (as defined by "fields" property in macro definition)
* Ticket description as plain text
* Change history
* Comment field

If user has TICKET_MODIFY and WIKI_MODIFY permissions, summary, description,
custom fields and comment are editable and changes can be saved by clicking
'Save' button.

Tickets can be removed from board by clicking 'Remove from board' button in
ticket detail dialog. Removing ticket from board does not modify or delete the
ticket.

If user has proper permissions ticket status can also be modified by dragging
tickets from one column to another. In this case ticket's new status is the
first status of destination column's "states" property.
