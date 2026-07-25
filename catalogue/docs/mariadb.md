to access mariadb:
using .env
cd ~/docker/slide-catalogue && set -a && source .env && set +a && docker exec -it catalogue_mariadb mariadb -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE"

root
cd ~/docker/slide-catalogue && set -a && source .env && set +a && docker exec -it catalogue_mariadb mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"

reference
cd ~/docker/slide-catalogue && set -a && source .env && set +a && docker exec catalogue_mariadb env | grep MARIADB
