import logging
import logging.handlers
import psycopg

base_logger = logging.getLogger("uvicorn")
base_logger.setLevel(logging.INFO)
base_handler = logging.handlers.RotatingFileHandler(
    "app/logs/ares.log", maxBytes=10000000, backupCount=5, encoding="utf-8"
)

base_formatter = logging.Formatter("%(asctime)s -- %(levelname)s -- %(message)s")
base_handler.setFormatter(base_formatter)

base_logger.addHandler(base_handler)

def get_database_logger():
    # Création du logger pour les commandes SQL
    sql_logger = logging.getLogger("sql_debug")
    sql_logger.setLevel(logging.INFO)

    # Configuration du handler pour écrire les logs dans un fichier
    sql_handler = logging.handlers.RotatingFileHandler(
        filename="app/logs/sql_debug.log",
        maxBytes=10485760,  # 10 Mo
        backupCount=1,
        encoding="utf-8",
    )

    # Configuration du formatter pour les logs SQL
    sql_formatter = logging.Formatter("%(asctime)s -- %(levelname)s -- %(message)s")
    sql_handler.setFormatter(sql_formatter)

    # Ajout du handler au logger
    sql_logger.addHandler(sql_handler)

    # Utilisation du logger personnalisé dans votre classe LoggingConnection
    class LoggingConnection(psycopg.Connection):
        def cursor(self, *args, **kwargs):
            return super().cursor(*args, **kwargs, cursor_factory=LoggingCursor)

    class LoggingCursor(psycopg.Cursor):
        def execute(self, query, params=None, *, prepare=None):
            formatted_query = self.connection.mogrify(query, params)
            sql_logger.info(formatted_query.decode())

            try:
                super().execute(query, params, prepare=prepare)
            except Exception as exc:
                sql_logger.error("%s: %s", exc.__class__.__name__, exc)
                raise

    return sql_logger, LoggingConnection

# Utilisation de LoggingConnection lors de la connexion à la base de données
# Exemple : conn = psycopg.connect(dsn="your_dsn", connection_factory=LoggingConnection)
