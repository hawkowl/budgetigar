
from __future__ import absolute_import

import click
import uuid
import hashlib

from axiom import item, attributes
from axiom.store import Store

from epsilon.extime import Time

from ofxparse import OfxParser

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
    transactions = list(store.query(Transaction))

    debit = 0
    credit = 0

    for t in transactions:
        if t.transactionType == "credit":
            credit += t.amount
        else:
            debit -= t.amount

    click.echo("There are {} accounts with {} transactions.".format(lenAccounts, len(transactions)))
    click.echo("There has been ${:2f} of debits and ${:2f} of credits.".format(debit, credit))


@cli.command()
def dumptransactions():

    transactions = list(store.query(Transaction))

    for x in transactions:
        print x

@cli.command()
def associate():
    """
    Associate transactions automatically.
    """
    _transactions = store.query(Transaction,
                                Transaction.related_transaction == None)

    possibleMatchesCount = 0

    with click.progressbar(_transactions, _transactions.count()) as transactions:
        for t in transactions:

            if not t.related_transaction:

                possibleMatches = store.query(Transaction,
                                              attributes.AND(
                                                  Transaction.amount == -t.amount,
                                                  Transaction.account != t.account,
                                                  Transaction.transactionID == t.transactionID,
                                                  Transaction.related_transaction == None
                                              )
                                          )

                if possibleMatches.count() == 1:
                    possibleMatchesCount += 1

                    match = list(possibleMatches)[0]

                    t.related_transaction = match.uuid
                    match.related_transaction = t.uuid


                elif possibleMatches.count() == 0:
                    pass

                else:
                    assert False


    click.echo("Associated {} matches.".format(possibleMatchesCount))




@cli.command()
@click.argument('f', type=click.File('r'))
def load(f):

    click.echo("Going to load {}...".format(f.name))

    ofx = OfxParser.parse(f)

    click.echo("Found {} accounts.".format(len(ofx.accounts)))

    for account in ofx.accounts:
        click.echo("Starting on {} account {} {}...".format(account.account_type.lower(),
                                                            account.routing_number,
                                                            account.account_id))

        storedAccounts = list(store.query(Account,
                                          attributes.AND(
                                              Account.routingNumber == unicode(account.routing_number),
                                              Account.accountID == unicode(account.account_id),
                                              Account.accountType == unicode(account.account_type)
                                          )))

        storedAccount = None

        if len(storedAccounts) == 0:

            click.echo("This seems to be a new account.")
            name = click.prompt("What do you want this account to be called?")

            storedAccount = Account(store=store,
                                    uuid=str(uuid.uuid4()),
                                    routingNumber=unicode(account.routing_number),
                                    accountID=unicode(account.account_id),
                                    accountType=unicode(account.account_type))

        elif len(storedAccounts) == 1:
            storedAccount = storedAccounts[0]
        else:
            assert False, "More than 1 account with this routing number + accid"

        click.echo("Found {} transactions.".format(len(account.statement.transactions)))

        modifiedCount = 0

        with click.progressbar(account.statement.transactions) as transactions:
            for t in transactions:

                if t.id == "":
                    # Hack for working around Commbank's lack of IDs sometimes
                    t.id = unicode("HACKFIX" + hashlib.sha224(
                        str(Time.fromDatetime(t.date).asPOSIXTimestamp) + str(t.amount) + t.memo).hexdigest())


                foundTransactions = list(store.query(Transaction,
                                                     attributes.AND(
                                                         Transaction.transactionID == t.id,
                                                         Transaction.amount == t.amount,
                                                         Transaction.account == storedAccount.uuid
                                                     )))

                if len(foundTransactions) == 0:

                    storedTransaction = Transaction(store=store,
                                                    uuid=str(uuid.uuid4()),
                                                    account=storedAccount.uuid,
                                                    transactionID=t.id,
                                                    transactionType=t.type,
                                                    postedDate=Time.fromDatetime(t.date),
                                                    amount=t.amount,
                                                    memo=t.memo)
                    modifiedCount = modifiedCount + 1

                elif len(foundTransactions) == 1:
                    pass
                    # skip
                else:
                    assert False, "More than one transaction in the account with the same ID"

        click.echo("{} transactions modified.".format(modifiedCount))
