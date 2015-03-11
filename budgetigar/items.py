import attr

from axiom import item, attributes

class Account(item.Item):
    """
    A bank account.
    """
    # Our UUID
    uuid = attributes.bytes(allowNone=False)

    # From the OFX
    routingNumber = attributes.text(allowNone=False)
    accountID = attributes.text(allowNone=False)
    accountType = attributes.text(allowNone=False)

    # User-given name
    accountName = attributes.text()

@attr.s(these={"account": attr.ib(),
               "uuid": attr.ib(),
               "transactionID": attr.ib(),
               "transactionType": attr.ib(),
               "date": attr.ib(),
               "_amount": attr.ib(),
               "_memo": attr.ib(),
               "related_transaction": attr.ib()
           },
        cmp=False, hash=False, init=False)
class Transaction(item.Item):
    """
    A transaction.
    """
    # Our UUID
    uuid = attributes.bytes(allowNone=False)

    # To link to an account
    account = attributes.bytes(allowNone=False)

    # From the OFX
    transactionID = attributes.text(allowNone=False)
    transactionType = attributes.text(allowNone=False)

    postedDate = attributes.timestamp(allowNone=False)

    amount = attributes.money(allowNone=False)
    memo = attributes.text()

    related_transaction = attributes.bytes()


    @property
    def date(self):
        return self.postedDate.asRFC2822()

    @property
    def _amount(self):
        return "{:2f}".format(self.amount)

    @property
    def _memo(self):
        return " ".join(self.memo.split())


class Budget(item.Item):
    """
    A budget (eg. "car insurance")
    """
    # Our UUID
    uuid = attributes.bytes(allowNone=False)

    name = attributes.text(allowNone=False)

    # When it first kicks in.
    startDate = attributes.timestamp(allowNone=False)

    # How much it should do by default
    defaultAmount = attributes.money()

    # Whether to make new months for it
    enabled = attributes.boolean(default=True)


class BudgetMonth(item.Item):

    budget = attributes.bytes(allowNone=False)
    # Eg. "2015-02"
    month = attributes.bytes(allowNone=False)
    amount = attributes.money(allowNone=False)



class TransactionAssociationExactRule(item.Item):
    budget = attributes.bytes(allowNone=False)
    memo = attributes.text()

class TransactionInBudget(item.Item):
    transaction = attributes.bytes(allowNone=False)
    budget = attributes.bytes(allowNone=False)
