import click

from axiom.store import Store


store = None

@click.group()
@click.argument("db", required=True)
def cli(db):
    global store
    store = Store(db)


@click.command()
def info():
    print "whee"
