set -e
export $(grep -v '^#' ../.env | xargs)
base_dir=$ROOT
cd $base_dir/docker/compose
docker stack deploy -c registry.yml registry