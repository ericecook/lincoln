from flask import current_app
from flask.ext.script import Manager
from decimal import Decimal

from lincoln import create_app, db, coinserv
from lincoln.models import Block, Transaction, Output

import datetime

manager = Manager(create_app)


@manager.command
def init_db():
    db.session.commit()
    db.drop_all()
    db.create_all()


@manager.command
def sync():
    # Get the current network info from the rpc server
    #curr_height = coinserv.getinfo()['blocks']
    #curr_hash = coinserv.getblockhash(curr_height)

    # Info about height from current database
    highest = Block.query.order_by(Block.height.desc()).first()

    #if not highest:
    #    common_ancestor = 0
    #else:
    #    # Find the last block shared between the servers
    #    while True:
    #        common_ancestor = Block.query.filter_by(hash=curr_hash).first()
    #        if common_ancestor:
    #            break
    #        current_app.logger.info(
    #            "Didn't find common ancestor at height {}, hsh {}"
    #            .format(curr_height, curr_hash))
    #        curr_height -= 1
    #        curr_hash = coinserv.getblockhash(curr_height)

    #current_app.logger.info(
    #    "Found common ancestor at {}".format(common_ancestor))

    while True:
        if not highest:
            curr_height = 0
        else:
            curr_height = highest.height + 1
        curr_hash = coinserv.getblockhash(curr_height)

        block = coinserv.getblock(curr_hash)
        block_obj = Block(hash=block.GetHash(),
                          height=curr_height,
                          ntime=datetime.datetime.utcfromtimestamp(block.nTime),
                          orphan=False,
                          total_value=Decimal(0),
                          difficulty=block.difficulty,
                          algo=current_app.config['algo']['display'],
                          currency=current_app.config['currency']['code'])
        db.session.add(block_obj)

        # all TX's in block are connectable; index
        for tx in block.vtx:
            tx_obj = Transaction(block=block_obj,
                                 txid=tx.GetHash())
            db.session.add(tx_obj)
            current_app.logger.info("Found new tx {}".format(tx_obj))

            total_out = Decimal(0)
            total_in = Decimal(0)

            if not tx.is_coinbase():
                for txin in tx.vin:
                    obj = Output.query.filter_by(
                        origin_tx_hash=txin.prevout.hash,
                        index=txin.prevout.n).one()
                    obj.spend_tx = tx_obj
                    total_in += obj.amount

            for i, txout in enumerate(tx.vout):
                out_dec = Decimal(txout.nValue) / 100000000
                block_obj.total_value += out_dec
                total_out += out_dec

                out = Output(origin_tx=tx_obj,
                             index=i,
                             amount=out_dec,
                             dest_address="")
                db.session.add(out)

        highest = block_obj
        db.session.commit()
        current_app.logger.info(
            "Synced block {}".format(block_obj))


manager.add_option('-c', '--config', default='/config.yml')
manager.add_option('-l', '--log-level',
                   choices=['DEBUG', 'INFO', 'WARN', 'ERROR'], default='INFO')

if __name__ == "__main__":
    manager.run()
