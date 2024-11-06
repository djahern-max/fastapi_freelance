import click
import requests
import os
import json
import logging
from typing import List, Optional

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.expanduser("~/.command_notes_config")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            logger.debug(f"Loaded config: {config}")
            return config
    default_config = {
        "api_url": "http://localhost:8000/command_notes",
        "user_id": 1,
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzMwNjcwMTE5fQ.l6ZJs0iGqivNM2lyvW8etrkQrI72Oqj9RTsB4Ullcao"
    }
    logger.debug(f"Using default config: {default_config}")
    return default_config

@click.group()
def cli():
    """Command Notes CLI - Save and retrieve terminal commands"""
    pass

@cli.command(name='create')
def create_deployment():
    """Create the deployment script"""
    config = load_config()
    
    deployment_data = {
        "title": "Deploy Frontend",
        "description": "Frontend deployment steps",
        "commands": [
            "sudo chown -R dane:www-data /var/www/html",
            "sudo rm -rf /var/www/html/*",
            "scp -r C:/Users/dahern/Documents/RYZE.ai/ryze-ai-frontend/build/* dane@161.35.96.28:/var/www/html/",
            "sudo chown -R www-data:www-data /var/www/html",
            r"sudo find /var/www/html/ -type d -exec chmod 755 {} \;",  # Fixed escape sequence
            r"sudo find /var/www/html/ -type f -exec chmod 644 {} \;",  # Fixed escape sequence
            "sudo systemctl restart nginx"
        ],
        "tags": ["deployment", "frontend"]
    }
    
    try:
        logger.debug(f"Creating deployment script with data: {deployment_data}")
        response = requests.post(
            f"{config['api_url']}/",
            params={"user_id": config["user_id"]},
            headers={
                "Authorization": f"Bearer {config['token']}",
                "Content-Type": "application/json"
            },
            json=deployment_data
        )
        response.raise_for_status()
        result = response.json()
        logger.debug(f"Created deployment script with response: {result}")
        click.echo("Created deployment script successfully!")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}", exc_info=True)
        click.echo(f"Error creating deployment script: {str(e)}", err=True)

@cli.command()
def list():
    """List all saved command notes"""
    config = load_config()
    
    try:
        response = requests.get(
            f"{config['api_url']}/",
            params={"user_id": config["user_id"]},
            headers={"Authorization": f"Bearer {config['token']}"}
        )
        response.raise_for_status()
        notes = response.json()
        
        if not notes:
            click.echo("No command notes found")
            return
            
        for note in notes:
            click.echo(f"\n{'='*50}")
            click.echo(f"Title: {note['title']}")
            click.echo(f"Description: {note['description']}")
            click.echo(f"Tags: {', '.join(note['tags'])}")
            click.echo("\nCommands:")
            for i, cmd in enumerate(note['commands'], 1):
                click.echo(f"{i}. {cmd}")
                
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}", exc_info=True)
        click.echo(f"Error listing notes: {str(e)}", err=True)

@cli.command()
@click.option('--dry-run', is_flag=True, help='Show commands without executing them')
def deploy(dry_run: bool):
    """Execute the frontend deployment script"""
    config = load_config()
    logger.debug("Starting deployment process")
    
    try:
        response = requests.get(
            f"{config['api_url']}/",
            params={"user_id": config["user_id"]},
            headers={"Authorization": f"Bearer {config['token']}"}
        )
        response.raise_for_status()
        notes = response.json()
        
        deployment_note = None
        for note in notes:
            if note['title'] == "Deploy Frontend":
                deployment_note = note
                break
        
        if not deployment_note:
            logger.error("No deployment script found")
            click.echo("Deployment script not found. Please run 'create' first.")
            return
        
        click.echo(f"\nFound deployment script: {deployment_note['title']}")
        click.echo(f"Description: {deployment_note['description']}")
        click.echo("\nCommands to execute:")
        for i, cmd in enumerate(deployment_note['commands'], 1):
            click.echo(f"{i}. {cmd}")
        
        if not dry_run and click.confirm('\nDo you want to execute these commands?'):
            for i, cmd in enumerate(deployment_note['commands'], 1):
                click.echo(f"\nExecuting step {i}: {cmd}")
                # Add actual command execution here if needed
                click.echo("Command executed successfully")
        else:
            click.echo("\nDry run - no commands were executed")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}", exc_info=True)
        click.echo(f"Error accessing API: {str(e)}", err=True)

if __name__ == '__main__':
    cli()