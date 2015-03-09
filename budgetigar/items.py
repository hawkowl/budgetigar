from axiom import item, attributes

class Account(item.Item):
    """
    A bank account.
    """
    # From the OFX
    bankID = attributes.bytes(allowNone=False)
    acctID = attributes.bytes(allowNone=False)
    acctType = attributes.bytes(allowNone=False)

    # User-given name
    acctName = attributes.bytes()


class Transaction(item.Item):
    """
    A transaction.
    """
    # From the OFX
    transactionID = attributes.bytes(allowNone=False)
    transactionType = attributes.bytes(allowNone=False)

    postedDate = attributes.bytes(allowNone=False)
    initiatedDate = attributes.bytes(allowNone=False)

    amount = attributes.money(allowNone=False)
    memo = attributes.bytes()
