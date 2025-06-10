export $(grep -v '^#' .env | xargs)
base_dir=$ROOT
cd $base_dir/docker/config/setup
docker build -f $base_dir/docker/compose/elk-setup.Dockerfile --build-arg ELASTIC_VERSION=${ELASTIC_VERSION} -t elk_setup:${ELASTIC_VERSION} --no-cache .
cd $base_dir/docker/compose
docker stack deploy -c elk.yml $ELK_STACK_NAME