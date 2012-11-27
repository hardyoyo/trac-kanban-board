from setuptools import setup, find_packages

setup(
    name='TracKanbanBoard',
    version='0.1',
    description="Kanban board plugin for Trac",
    long_description="""\
    """,
    classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='Arto Nyk\xc3\xa4nen',
    author_email='arto.nykanen@digia.com',
    url='',
    license='',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    package_data={
        'trackanbanboard': [
            'templates/*.html',
            'htdocs/css/*.css',
            'htdocs/css/images/*.png',
            'htdocs/js/*.js',
            'htdocs/js/libs/*.js'
        ]
    },
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # -*- Extra requirements: -*-
    ],
    entry_points="""
        [trac.plugins]
        trackanbanboard = trackanbanboard
    """,
)
