from datetime import datetime

import psycopg2
from psycopg2 import sql
from blockchain import Block, Blockchain

# Custom exceptions for transaction errors
class InvalidTransactionException(Exception): pass
class InsufficientFundsException(Exception): pass

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="crypto",
        user="postgres",
        password="postgres",
        # Add these parameters for better connection handling
        connect_timeout=3,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )



class Table():
    def __init__(self, conn, table_name, *args):
        self.conn = conn
        self.table = table_name
        self.columns = ",".join(args)
        self.columnsList = args

        if self.isnewtable():
            create_data = ", ".join([f"{column} VARCHAR(100)" for column in self.columnsList])
            with self.conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE TABLE {} ({})").format(
                    sql.Identifier(self.table),
                    sql.SQL(create_data)
                ))
            self.conn.commit()



    def isnewtable(self):
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT to_regclass(%s)"), (self.table,))
            return cur.fetchone()[0] is None

    def getall(self):
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(self.table)))
            results = cur.fetchall()
            return [dict(zip(self.columnsList, row)) for row in results]

    def getone(self, search, value):
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT * FROM {} WHERE {} = %s").format(
                sql.Identifier(self.table),
                sql.Identifier(search)
            ), (value,))
            result = cur.fetchone()
            if result:
                return dict(zip(self.columnsList, result))
            return None

    def deleteone(self, search, value):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("DELETE FROM {} WHERE {} = %s").format(
                    sql.Identifier(self.table),
                    sql.Identifier(search)
                ), (value,))
                conn.commit()

    def deleteall(self):
        self.drop()
        self.__init__(self.table, *self.columnsList)

    def drop(self):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(self.table)))
                conn.commit()

    def insert(self, *args):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(args))
                cur.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(self.table),
                    sql.SQL(self.columns),
                    sql.SQL(placeholders)
                ), args)
                conn.commit()




def sql_raw(execution):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(execution)
            conn.commit()

def isnewuser(username):
    users = Table("users", "name", "email", "username", "password")
    data = users.getall()
    usernames = [user[2] for user in data]
    return username not in usernames

# Add this to sqlhelpers.py

def update_balance(username, new_balance, conn):
    """Update user balance in the database"""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET balance = %s WHERE username = %s",
                (new_balance, username)
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Failed to update balance: {str(e)}")


# Update in sqlhelpers.py

def send_money(sender, recipient, amount):
    print(f"Starting send_money: sender={sender}, recipient={recipient}, amount={amount}")
    try:
        amount = float(amount)

        with get_db_connection() as conn:
            print("Got database connection")
            conn.autocommit = False

            try:
                # Previous validation and balance update code remains the same...

                # Update blockchain
                blockchain = get_blockchain(conn)
                number = len(blockchain.chain) + 1
                data = f"{sender}-->{recipient}-->{amount}"
                print(f"Adding to blockchain: {data}")
                blockchain.mine(Block(number, data=data))

                # Sync blockchain with better error handling
                print("Starting blockchain sync")
                try:
                    sync_blockchain(blockchain)
                    print("Blockchain sync completed")
                except Exception as e:
                    print(f"Error during blockchain sync: {str(e)}")
                    raise e

                print("Committing transaction")
                conn.commit()
                print("Transaction committed successfully")
                return True

            except Exception as e:
                print(f"Error in transaction: {str(e)}")
                conn.rollback()
                raise e
            finally:
                conn.autocommit = True

    except ValueError:
        raise InvalidTransactionException("Invalid transaction amount")
    except Exception as e:
        print(f"Outer error in send_money: {str(e)}")
        raise Exception(f"Transaction failed: {str(e)}")


def get_transaction_history(username, limit=10):
    """Get transaction history for a user"""
    try:
        with get_db_connection() as conn:
            blockchain = get_blockchain(conn)
            transactions = []

            for block in reversed(blockchain.chain):
                data = block.data.split("-->")
                sender, recipient, amount = data[0], data[1], float(data[2])

                if username in (sender, recipient):
                    transaction = {
                        'date': block.timestamp if hasattr(block, 'timestamp') else datetime.now(),
                        'type': 'RECEIVED' if username == recipient else 'SENT',
                        'amount': amount,
                        'status': 'COMPLETED',
                        'sender': sender,
                        'recipient': recipient
                    }
                    transactions.append(transaction)

                if len(transactions) >= limit:
                    break

            return transactions
    except Exception as e:
        raise Exception(f"Failed to get transaction history: {str(e)}")

def get_balance(username, conn):
    """Get current balance from the database"""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM users WHERE username = %s",
                (username,)
            )
            result = cur.fetchone()
            if result:
                return float(result[0])
            return 0.0
    except Exception as e:
        raise Exception(f"Failed to get balance: {str(e)}")

def get_blockchain(conn):
    blockchain = Blockchain()
    blockchain_sql = Table(conn, "blockchain", "number", "hash", "previous", "data", "nonce")
    for b in blockchain_sql.getall():
        blockchain.add(Block(int(b['number']), b['previous'], b['data'], int(b['nonce'])))
    return blockchain

def sync_blockchain(blockchain):
    """Sync blockchain with database"""
    with get_db_connection() as conn:
        blockchain_sql = Table(conn, "blockchain", "number", "hash", "previous", "data", "nonce")
        blockchain_sql.deleteall()

        for block in blockchain.chain:
            blockchain_sql.insert(str(block.number), block.hash(), block.previous_hash, block.data, block.nonce)