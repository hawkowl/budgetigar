
from __future__ import absolute_import

import click

from axiom.store import Store

from budgetigar.items import Account, Transaction


store = None

@click.group()
@click.argument("db", required=True)
def cli(db):
    global store
    store = Store(db)


@cli.command()
def info():

    lenAccounts = store.query(Account).count()
    lenTransactions = store.query(Transaction).count()

    click.echo("There are {} accounts with {} transactions.".format(lenAccounts, lenTransactions))


@cli.command()
@click.argument('f', type=click.Path(exists=True))
def load(f):

    click.echo("Going to load {}...".format(click.format_filename(f)))
