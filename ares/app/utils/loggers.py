import logging
import logging.handlers
import psycopg2

def get_base_logger():
    base_logger = logging.getLogger("uvicorn")
    base_logger.setLevel(logging.INFO)
    base_handler = logging.handlers.RotatingFileHandler(
        "app/logs/ares.log", 
        maxBytes=10000000, 
        backupCount=5, 
        encoding="utf-8"
    )

    base_formatter = logging.Formatter("%(asctime)s -- %(levelname)s -- %(message)s")
    base_handler.setFormatter(base_formatter)

    base_logger.addHandler(base_handler)
    return base_logger

def get_database_logger():
    # Création du logger pour les commandes SQL
    sql_logger = logging.getLogger("sql_debug")
    sql_logger.setLevel(logging.INFO)

    # Configuration du handler pour écrire les logs dans un fichier
    sql_handler = logging.handlers.RotatingFileHandler(
        filename="app/logs/sql_debug.log",
        maxBytes=1048576,  # 1 Mo
        backupCount=5,
        encoding="utf-8"
    )

    # Configuration du formatter pour les logs SQL
    sql_formatter = logging.Formatter("%(asctime)s -- %(levelname)s -- %(message)s")
    sql_handler.setFormatter(sql_formatter)

    # Ajout du handler au logger
    sql_logger.addHandler(sql_handler)

    # Utilisation du logger personnalisé dans votre classe LoggingCursor
    class LoggingCursor(psycopg2.extensions.cursor):
        def execute(self, sql, args=None):
            sql_logger.info(self.mogrify(sql, args))

            try:
                psycopg2.extensions.cursor.execute(self, sql, args)
            except Exception as exc:
                sql_logger.error("%s: %s" % (exc.__class__.__name__, exc))
                raise
            
    return sql_logger, LoggingCursor