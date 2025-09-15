"""
Command-line interface for PeakFlow Tasks.

This module provides CLI commands for starting workers, beat scheduler, monitoring, and development.
"""

import click
import os
import sys
from typing import Optional

from peakflow_tasks.celery_app import celery_app
from peakflow_tasks.config import get_settings


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool) -> None:
    """PeakFlow Tasks command-line interface."""
    if debug:
        os.environ["DEBUG"] = "true"


@cli.command()
@click.option("--concurrency", "-c", default=4, help="Number of worker processes")
@click.option("--loglevel", "-l", default="info", help="Logging level")
@click.option("--queues", "-Q", help="Comma-separated list of queues to consume")
@click.option("--hostname", "-n", help="Worker hostname")
def worker(concurrency: int, loglevel: str, queues: Optional[str], hostname: Optional[str]) -> None:
    """Start Celery worker."""
    args = ["worker"]
    
    args.extend(["--concurrency", str(concurrency)])
    args.extend(["--loglevel", loglevel])
    
    if queues:
        args.extend(["--queues", queues])
    
    if hostname:
        args.extend(["--hostname", hostname])
    
    # Add event monitoring
    args.append("--events")
    
    click.echo(f"Starting Celery worker with args: {' '.join(args)}")
    celery_app.worker_main(args)


@cli.command()
@click.option("--loglevel", "-l", default="info", help="Logging level")
@click.option("--schedule", "-s", help="Path to schedule file")
def beat(loglevel: str, schedule: Optional[str]) -> None:
    """Start Celery beat scheduler."""
    args = ["beat"]
    
    args.extend(["--loglevel", loglevel])
    
    if schedule:
        args.extend(["--schedule", schedule])
    
    click.echo(f"Starting Celery beat with args: {' '.join(args)}")
    celery_app.start(args)


@cli.command()
@click.option("--port", "-p", default=5555, help="Port for Flower web interface")
@click.option("--basic-auth", help="Basic authentication (user:password)")
def flower(port: int, basic_auth: Optional[str]) -> None:
    """Start Flower monitoring interface."""
    try:
        from flower.command import FlowerCommand
    except ImportError:
        click.echo("❌ Flower is not installed. Install with: uv add flower", err=True)
        sys.exit(1)
    
    args = [
        "--broker", celery_app.conf.broker_url,
        "--port", str(port),
    ]
    
    if basic_auth:
        args.extend(["--basic-auth", basic_auth])
    
    click.echo(f"Starting Flower on port {port}")
    flower_cmd = FlowerCommand()
    flower_cmd.execute_from_commandline(["flower"] + args)


@cli.command()
def status() -> None:
    """Check status of Celery workers."""
    try:
        # Check if workers are active
        stats = celery_app.control.inspect().stats()
        
        if not stats:
            click.echo("❌ No active workers found")
            sys.exit(1)
        
        click.echo("✅ Active workers:")
        for worker, info in stats.items():
            click.echo(f"  • {worker}: {info.get('total', 'unknown')} tasks processed")
        
        # Check queues
        active_queues = celery_app.control.inspect().active_queues()
        if active_queues:
            click.echo("\n📋 Active queues:")
            for worker, queues in active_queues.items():
                queue_names = [q['name'] for q in queues]
                click.echo(f"  • {worker}: {', '.join(queue_names)}")
        
    except Exception as e:
        click.echo(f"❌ Error checking status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--queue", "-q", help="Purge specific queue")
def purge(queue: Optional[str]) -> None:
    """Purge task queues."""
    if queue:
        click.echo(f"Purging queue: {queue}")
        celery_app.control.purge()
    else:
        if click.confirm("⚠️  This will purge ALL queues. Continue?"):
            click.echo("Purging all queues...")
            celery_app.control.purge()
        else:
            click.echo("Cancelled")


@cli.command()
def inspect() -> None:
    """Inspect running workers and tasks."""
    try:
        # Active tasks
        active = celery_app.control.inspect().active()
        if active:
            click.echo("🔄 Active tasks:")
            for worker, tasks in active.items():
                click.echo(f"  Worker: {worker}")
                for task in tasks:
                    click.echo(f"    • {task['name']} [{task['id']}]")
        else:
            click.echo("✅ No active tasks")
        
        # Scheduled tasks
        scheduled = celery_app.control.inspect().scheduled()
        if scheduled and any(scheduled.values()):
            click.echo("\n⏰ Scheduled tasks:")
            for worker, tasks in scheduled.items():
                if tasks:
                    click.echo(f"  Worker: {worker}")
                    for task in tasks:
                        click.echo(f"    • {task['request']['task']} at {task['eta']}")
        
        # Reserved tasks
        reserved = celery_app.control.inspect().reserved()
        if reserved and any(reserved.values()):
            click.echo("\n📋 Reserved tasks:")
            for worker, tasks in reserved.items():
                if tasks:
                    click.echo(f"  Worker: {worker}")
                    for task in tasks:
                        click.echo(f"    • {task['name']} [{task['id']}]")
        
    except Exception as e:
        click.echo(f"❌ Error inspecting workers: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--concurrency", "-c", default=1, help="Number of worker processes (default: 1 for dev)")
@click.option("--log-level", "-l", default="info", help="Logging level (default: info)")
@click.option("--queues", "-q", default="celery,workflows", help="Queues to consume")
@click.option("--watch/--no-watch", default=False, help="Enable file watching and auto-restart")
@click.option("--flower/--no-flower", default=False, help="Also start Flower monitoring")
@click.option("--beat/--no-beat", default=False, help="Also start Celery beat scheduler")
@click.option("--env-file", default=None, help="Path to .env file")
@click.option("--check-deps/--no-check-deps", default=True, help="Check dependencies before starting")
@click.option("--pool", default="prefork", help="Worker pool type (default: prefork for dev)")
@click.option("--hostname", default=None, help="Worker hostname")
def dev(
    concurrency: int,
    log_level: str, 
    queues: str,
    watch: bool,
    flower: bool,
    beat: bool,
    env_file: Optional[str],
    check_deps: bool,
    pool: str,
    hostname: Optional[str]
) -> None:
    """Start development environment with enhanced features."""
    try:
        from peakflow_tasks.dev import DevRunner, DevConfig
    except ImportError as e:
        click.echo(f"❌ Failed to import development runner: {e}", err=True)
        click.echo("💡 Try installing dev dependencies: uv add --dev watchdog colorama python-dotenv")
        sys.exit(1)
    
    # Create configuration
    config = DevConfig(
        concurrency=concurrency,
        log_level=log_level,
        queues=queues,
        watch=watch,
        flower=flower,
        beat=beat,
        env_file=env_file,
        check_deps=check_deps,
        pool=pool,
        hostname=hostname
    )
    
    # Create and run development environment
    runner = DevRunner(config)
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()