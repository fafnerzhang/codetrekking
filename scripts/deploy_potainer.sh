export $(grep -v '^#' .env | xargs)
base_dir=$ROOT
cd $base_dir/docker/compose
docker stack deploy -c potainer-agent.yml $PORTAINER_STACK_NAME