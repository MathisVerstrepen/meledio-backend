#!/bin/bash
# sudo sh recreate_db.sh

# Nom de l'utilisateur PostgreSQL
DB_USER="postgres"
DB_PORT="5432"
DB_HOST="65.21.91.39"
DB_PASSWORD="3VPZj2ipBGQTtRgutnv9759TM6HLB49VNFm96sXiP4XzshUEg7fPd5iernNFhqaF"

# Nom du volume Docker de la base de données
VOLUME_NAME="db"

# Nom du fichier de sauvegarde
BACKUP_FILE="db_save.dump"

# Répertoire local pour stocker la sauvegarde
BACKUP_DIR="/home/mathis/dune/docker/backups"

# Créer une sauvegarde de la base de données
PGPASSWORD="3VPZj2ipBGQTtRgutnv9759TM6HLB49VNFm96sXiP4XzshUEg7fPd5iernNFhqaF" pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -Fc postgres -v > $BACKUP_DIR/$BACKUP_FILE


# Arrêter le conteneur Docker
docker compose -f back-compose.yml down

# Supprimer le dossier associé à la base de données
rm -rf /home/mathis/dune/docker/volumes/$VOLUME_NAME

# Démarrer un nouveau conteneur Docker
docker compose -f back-compose.yml up -d

# Rétablir la base de données à partir de la sauvegarde
# docker exec -i iris pg_restore -c -U postgres -h 127.0.0.1 -d postgres < $BACKUP_DIR/$BACKUP_FILE
