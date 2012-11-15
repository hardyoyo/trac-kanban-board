import os.path

from trac.core import implements
from trac.wiki.macros import WikiMacroBase
from trac.web.chrome import ITemplateProvider, Chrome, add_stylesheet, add_script

class KanbanBoardMacro(WikiMacroBase):
    """Insert Kanban board into the wiki page."""

    implements(ITemplateProvider)

    revision = "$Rev$"
    url = "$URL$"

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('trackanbanboard', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('kbm', os.path.abspath(resource_filename('trackanbanboard', 'htdocs')))]

    def expand_macro(self, formatter, name, text):
        data = {'title': 'Kanban board'}
        add_script(formatter.req, 'kbm/js/kanbanboard.js')
        add_stylesheet(formatter.req, 'kbm/css/kanbanboard.css')
        return Chrome(self.env).render_template(formatter.req,
            'kanbanboard.html',
            data,
            None,
            fragment=True).render(strip_whitespace=False)
