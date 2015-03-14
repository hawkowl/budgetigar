
from __future__ import absolute_import

import click
import uuid
import hashlib

from decimal import Decimal

from datetime import datetime
from dateutil.relativedelta import relativedelta

from axiom import item, attributes
from axiom.attributes import AND, LikeComparison, LikeValue
from axiom.store import Store

from epsilon.extime import Time

from ofxparse import OfxParser

from budgetigar.items import Account, Transaction, Budget, BudgetMonth, TransactionInBudget, TransactionAssociationExactRule


store = None

@click.group()
@click.argument("db", required=True)
def cli(db):
    """
    A budget and money tracking tool.
    """
    global store
    store = Store(db)


@cli.command()
def info():
    """
    Display some info about the database.
    """
    lenAccounts = store.query(Account).count()
    transactions = list(store.query(Transaction))

    debit = 0
    credit = 0

    for t in transactions:
        if not t.related_transaction:
            if t.transactionType == "credit":
                credit += t.amount
            else:
                debit -= t.amount

    click.echo("There are {} accounts with {} transactions.".format(lenAccounts, len(transactions)))
    click.echo("There has been ${:2f} of debits and ${:2f} of credits (external).".format(debit, credit))


@cli.command()
def dumptransactions():
    """
    Dump all the transactions.
    """
    transactions = list(store.query(Transaction))

    for x in transactions:
        print x

@cli.group()
def budget():
    """
    Budgeting commands.
    """

@budget.command(name="add")
def budget_add():

    name = click.prompt("What name should this budget have?")
    cost = click.prompt("How much is it per month?", type=Decimal)
    stdDate = click.prompt("When is the first instance? YYYY-MM")

    startDate = Time.fromISO8601TimeAndDate(stdDate + "-01")

    b = Budget(
        store=store,
        uuid=str(uuid.uuid4()),

        name=name,
        startDate=startDate,
        defaultAmount=cost)


@budget.command(name="maintainall")
def budget_maintainall():

    budgets = map(lambda d: d.startDate, store.query(Budget,
                                                     AND(
                                                         Budget.enabled == True,
                                                     )))

    budgets.sort()

    startDate = budgets[0].asDatetime()

    startYear = startDate.year
    startMonth = startDate.month

    now = Time().asDatetime()

    for year in range(startYear, now.year+1):

        if year == startYear:
            beginMonth = startMonth
        else:
            beginMonth = 1

        if year == now.year:
            endMonth = now.month+1
        else:
            endMonth = 13

        for month in range(beginMonth, endMonth):


            budget_maintain("{}-{}".format(year, month))



def budget_maintain(month):

    if not month:
        now = Time().asDatetime()
        month = "{}-{:02d}".format(now.year, now.month)
    else:
        month = "{}-{:02d}".format(*map(int, month.encode("utf8").split("-")))

    monthDatetime = Time.fromISO8601TimeAndDate(month + "-01")



    budgets = store.query(Budget,
                          AND(
                              Budget.enabled == True,
                              Budget.startDate <= monthDatetime
                          ))

    budgetMonths = [x.budget for x in store.query(BudgetMonth,
                                                  BudgetMonth.month == month)]

    for budget in budgets:

        if budget.uuid not in budgetMonths:

            BudgetMonth(store=store,
                        budget=budget.uuid,
                        month=month,
                        amount=budget.defaultAmount)

    click.echo("Done {}".format(month))

def getUnassociatedTransactions():

    alltrans = store.query(Transaction,
                           Transaction.related_transaction == None)
    budgetTransactions = [x.transaction for x in store.query(TransactionInBudget)]

    trans = [x for x in alltrans if x.uuid not in budgetTransactions]

    return trans


@budget.command(name="showunassociated")
def budget_showunassociated():

    trans = getUnassociatedTransactions()

    for item in trans:
        click.echo("{} on {} for {}".format(item._memo, item.postedDate, item.amount))

    print len(trans)

@budget.command(name="showmonth")
def budget_showmonth():

    budgets = store.query(Budget,
                          Budget.enabled == True)

    budgetedMonths = list(set(
        map(lambda d: tuple(map(int, d.month.split("-"))), list(store.query(BudgetMonth)))
    ))
    budgetedMonths.sort()

    c = " {: <7} | {: <8} | {: <8} | {: <8} | {: <8} | {: <8} | {: <8}"

    click.echo("{:-^74}".format(""))
    click.echo(c.format(" ", "Budgeted", "Budgeted", "Non-budg",  "", "Month", "Total"))
    click.echo(c.format("Month", "Forecast", " Spent", " Spent",  "Income", "Buffer", "Buffer"))
    click.echo("{:-^74}".format(""))

    totalAmount = 0

    for year, month in budgetedMonths:

        d = relativedelta(months=1)

        windowStart = datetime(year=year, month=month, day=1)

        budgetMonths = store.query(BudgetMonth,
                                   BudgetMonth.month == "{}-{:02d}".format(year, month))

        budgetedCost = Decimal(0)
        budgetedForecast = 0
        totalCost = Decimal(0)
        income = Decimal(0)

        for m in budgetMonths:

            windowtrans = store.query(Transaction,
                                      AND(
                                          TransactionInBudget.budget == m.budget,
                                          TransactionInBudget.transaction == Transaction.uuid,
                                          Transaction.postedDate >= Time.fromDatetime(windowStart),
                                          Transaction.postedDate < Time.fromDatetime(windowStart + d),
                                          Transaction.amount < 0
                                      ))

            for t in windowtrans:
                budgetedCost += -t.amount

            budgetedForecast += m.amount

        # Monthly unbudgeted costs
        monthTrans = store.query(Transaction,
                                 AND(
                                     Transaction.related_transaction == None,
                                     Transaction.postedDate >= Time.fromDatetime(windowStart),
                                     Transaction.postedDate < Time.fromDatetime(windowStart + d),
                                     Transaction.amount < 0
                                 ))

        for t in monthTrans:
            totalCost = totalCost + -t.amount

        # Monthly income
        monthIncome = store.query(Transaction,
                                 AND(
                                     Transaction.related_transaction == None,
                                     Transaction.postedDate >= Time.fromDatetime(windowStart),
                                     Transaction.postedDate < Time.fromDatetime(windowStart + d),
                                     Transaction.amount > 0
                                 ))

        for t in monthIncome:
            income += t.amount

        margin = income - totalCost

        if margin >= 0:
            fgcol = "green"
        else:
            fgcol = "red"

        totalAmount += margin

        click.secho(" {: <7} | {:>8.2f} | {:>8.2f} | {:>8.2f} | {:>8.2f} | {:>8.2f} | {:>8.2f}".format("{}-{:02d}".format(year, month), budgetedForecast, budgetedCost, totalCost-budgetedCost, income, margin, totalAmount), fg=fgcol)


@budget.command(name="show")
def budget_show():

    budgets = store.query(Budget,
                          Budget.enabled == True)

    d = relativedelta(months=1)

    for i in budgets:

        click.echo("{:=^39}".format(""))
        click.echo(" {}:".format(i.name))


        budgetMonths = list(store.query(BudgetMonth,
                                        BudgetMonth.budget == i.uuid
                                    ))

        budgetMonths.sort(key=lambda f: f.month.split("-"))


        click.echo("{:-^39}".format(""))
        click.echo(" {0: <7} | {1: <7} | {2: <7} | {3: <7}".format("Month", "Budget", "Spent", "Margin"))
        click.echo("{:-^39}".format(""))

        lastMonth = 0

        for month in budgetMonths:

            y,m = map(int, month.month.split("-"))

            windowStart = datetime(year=y, month=m, day=1)

            windowtrans = store.query(Transaction,
                                      AND(
                                          TransactionInBudget.budget == i.uuid,
                                          TransactionInBudget.transaction == Transaction.uuid,
                                          Transaction.postedDate >= Time.fromDatetime(windowStart),
                                          Transaction.postedDate < Time.fromDatetime(windowStart + d)
                                      ))

            cost = 0

            for t in windowtrans:
                cost = cost + -t.amount

            margin = lastMonth + month.amount - cost

            if margin >= 0:
                fgcol = "green"
            else:
                fgcol = "red"

            click.secho(" {: <7} | {:>7.2f} | {:>7.2f} | {:>7.2f}".format(month.month, month.amount, cost, margin), fg=fgcol)


            lastMonth = margin


@budget.command(name="list")
def budget_list():

    budgetItems = store.query(Budget,
                              Budget.enabled == True)

    for item in budgetItems:
        print item

@budget.command(name="runrules")
def budget_runrules():

    budgets = {x.uuid:x for x in store.query(Budget, Budget.enabled == True)}
    rules = store.query(TransactionAssociationExactRule)

    for rule in rules:

        if rule.budget in budgets.keys():

            click.echo("Doing '{}' for {}".format(rule.memo, budgets[rule.budget].name))

            searchParts = [LikeValue(u"%{}%".format(rule.memo))]

            items = list(store.query(Transaction,
                                     LikeComparison(Transaction.memo,
                                                    False, searchParts)
                                 ))

            allowedTransactions = [x.uuid for x in getUnassociatedTransactions()]

            items = [x for x in items if x.uuid in allowedTransactions]

            for item in items:
                click.echo("{} on {} for {}".format(item._memo, item.postedDate, item.amount))

            if click.confirm('Does this look good?'):
                found = True

                budget = budgets[rule.budget]

                with click.progressbar(items) as ix:

                    for item in ix:

                        TransactionInBudget(
                            store=store,
                            transaction=item.uuid,
                            budget=budget.uuid)



        else:
            click.echo("Disabled budget")


@budget.command(name="dumprules")
def budget_dumprules():

    budgets = {x.uuid:x for x in store.query(Budget, Budget.enabled == True)}
    rules = store.query(TransactionAssociationExactRule)

    for rule in rules:
        click.echo("'{}' matches to {}".format(rule.memo, budgets[rule.budget].name))





@budget.command(name="associate")
def budget_associate():

    found = False

    while found == False:

        imp = click.prompt("Name")

        searchParts = [LikeValue(u"%{}%".format(imp.encode()))]

        bi = list(store.query(Budget,
                              AND(
                                  Budget.enabled == True,
                                  LikeComparison(Budget.name,
                                                 False, searchParts)
                              )))

        if len(bi) == 1:
            found = True
        else:
            click.echo("NOPE")

    budget = bi[0]

    click.echo("Found budget {}".format(budget.name))

    found = False

    while found == False:

        imp = click.prompt("Memo Name")

        searchParts = [LikeValue(u"%{}%".format(imp))]

        items = list(store.query(Transaction,
                                  LikeComparison(Transaction.memo,
                                                 False, searchParts)
                              ))

        allowedTransactions = [x.uuid for x in getUnassociatedTransactions()]

        items = [x for x in items if x.uuid in allowedTransactions]

        for item in items:
            click.echo("{} on {} for {}".format(item._memo, item.postedDate, item.amount))

        if click.confirm('Does this look good?'):
            found = True

    alreadyAssociatedItems = list(x.transaction for x in store.query(TransactionInBudget,
                                                                      TransactionInBudget.budget == budget.uuid))

    with click.progressbar(items) as ix:

        for item in ix:

            if item.uuid not in alreadyAssociatedItems:

                TransactionInBudget(
                    store=store,
                    transaction=item.uuid,
                    budget=budget.uuid)

    if click.confirm("Do you want to add this as an exact rule?"):
        TransactionAssociationExactRule(store=store,
                                        budget=budget.uuid,
                                        memo=imp)

    click.echo("Done!")




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
    """
    Load in an OFX data file.
    """
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
