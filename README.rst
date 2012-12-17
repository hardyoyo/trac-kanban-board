Main features
=============

- Define board columns and how they map to ticket states
- Change ticket state by dragging tickets on the board
- Add existing tickets to board by drag-and-dropping ticket links
- Create new tickets directly from board
- View and modify ticket fields (summary, description, etc.) and add comments from ticket detail dialog
- Define what ticket fields are visible on ticket detail dialog

Data storage
============

Plugin uses Trac tickets as kanban board "cards". Any existing ticket from project can be added to the board and modifed either from board or from default Trac ticket view.

All kanban board specific information (such as column definitions and card order) is stored in macro definition on wiki page. When cards are moved around plugin updates the macro definition and rewrites wiki page.

Installation
============

#. Clone the repository::

    git clone https://projects.developer.nokia.com/git/TracKanbanBoard.git trackanbanboard

#. Run setup script::

    cd trackanbanboard
    python setup.py install

#. Enable component in Trac configuration::

    [components]
    trackanbanboard.* = enabled

#. Create/modify wiki page and put `KanbanBoard` processor in it. Empty data will given an error but also the detailed usage instructions::

    This is wiki text:
    {{{
    #!KanbanBoard
    }}}

Here's an example macro definition that produces Kanban board with three columns (New, Ongoing and Done)::

    {{{
    #!KanbanBoard height=250px
    {
      "columns": [
        { "id": 1, "name": "New", "states": ["new"], "tickets": [23, 24, 25], "wip": 3 },
        { "id": 2, "name": "Ongoing", "states": ["assigned", "accepted", "reopened"], "tickets": [21], "wip": 3 },
        { "id": 3, "name": "Done", "states": ["closed"], "tickets": [22], "wip": 5 }
      ],
      "fields": [
        "status", "priority", "type", "keywords"
      ]
    }
    }}}

You can also use `[[MacroList(KanbanBoard)]]` macro to see full documentation.

