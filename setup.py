import os
from setuptools import setup, find_packages

setup(
    name = 'TracKanbanBoard',
    version = '0.1',
    description = "Kanban board plugin for Trac",
    long_description = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read(),
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'Framework :: Trac',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python'
    ],
    keywords = 'trac plugin kanban',
    author = 'Arto Nyk\xc3\xa4nen',
    author_email = 'arto.nykanen@digia.com',
    url = 'http://projects.developer.nokia.com/TracKanbanBoard',
    license = 'BSD-new',
    packages = find_packages(exclude=['ez_setup', 'examples', 'tests']),
    package_data = {
        'trackanbanboard': [
            'templates/*.html',
            'htdocs/css/*.css',
            'htdocs/css/images/*.png',
            'htdocs/js/*.js',
            'htdocs/js/libs/*.js'
        ]
    },
    include_package_data = True,
    zip_safe = False,
    install_requires = ['Trac'],
    entry_points = """
        [trac.plugins]
        trackanbanboard = trackanbanboard
    """,
)
