from setuptools import setup

setup(
    name='budgetigar',
    version='0.1',
    py_modules=['budgetigar'],
    install_requires=[
        'Click',
        'axiom',
        'ofxparse',
        'attrs'
    ],
    entry_points='''
        [console_scripts]
        budgetigar=budgetigar.cli:cli
    ''',
)
