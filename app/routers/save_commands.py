
        # app/cli/save_commands.py
import click
import requests
import os
import json
import subprocess
import getpass
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from urllib.parse import urlparse

CONFIG_FILE = os.path.expanduser("~/.command_notes_config")
DEFAULT_ENV = "prod"

# Environment configurations
ENVIRONMENTS: Dict[str, Dict[str, str]] = {
    "prod": {
        "api": "https://www.ryze.ai",
        "frontend": "https://ryze.ai"
    },
    "prod_www": {
        "api": "https://www.ryze.ai",
        "frontend": "https://www.ryze.ai"
    },
    "dev": {
        "api": "http://127.0.0.1:8000",
        "frontend": "http://localhost:3000"
    },
    "dev_alt": {
        "api": "http://127.0.0.1:8000",
        "frontend": "http://localhost:3002"
    }
}

class AuthenticationError(Exception):
    pass

class ConfigurationError(Exception):
    pass

def get_urls(config: dict) -> tuple[str, str]:
    """Get API and frontend URLs based on environment"""
    env = config.get('environment', DEFAULT_ENV)
    if env not in ENVIRONMENTS:
        raise ConfigurationError(f"Invalid environment: {env}")
    
    env_config = ENVIRONMENTS[env]
    return env_config["api"], env_config["frontend"]

def validate_url(url: str) -> bool:
    """Validate if URL is in allowed origins"""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    allowed_origins = [
        ENVIRONMENTS[env]["api"] for env in ENVIRONMENTS
    ] + [
        ENVIRONMENTS[env]["frontend"] for env in ENVIRONMENTS
    ]
    return base_url in allowed_origins

def validate_token(token: str, api_url: str) -> bool:
    """Validate token with the auth endpoint"""
    try:
        response = requests.get(
            f"{api_url}/auth/validate-token",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def get_user_info(token: str, api_url: str) -> dict:
    """Get user information using the token"""
    try:
        response = requests.get(
            f"{api_url}/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise AuthenticationError(f"Failed to get user info: {str(e)}")

def get_token(username: str, password: str, api_url: str) -> dict:
    """Authenticate user and get token"""
    try:
        response = requests.post(
            f"{api_url}/auth/login",
            data={"username": username, "password": password}
        )
        response.raise_for_status()
        token_data = response.json()
        
        user_info = get_user_info(token_data['access_token'], api_url)
        
        return {
            'access_token': token_data['access_token'],
            'user_id': user_info['id'],
            'username': user_info['username']
        }
    except requests.exceptions.RequestException as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")

def load_config():
    """Load configuration or create new if doesn't exist"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            api_url, _ = get_urls(config)
            if not config.get('token') or not validate_token(config['token'], api_url):
                config = refresh_authentication(config)
            return config
    return {
        "environment": DEFAULT_ENV,
        "user_id": None,
        "token": None,
        "username": None
    }

def save_config(config: dict):
    """Save configuration to file"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def refresh_authentication(config: dict) -> dict:
    """Refresh authentication if needed"""
    api_url, _ = get_urls(config)
    
    if not config.get('username'):
        username = click.prompt('Username')
    else:
        username = config['username']
        click.echo(f"Reauthenticating as {username}")
    
    password = click.prompt('Password', hide_input=True)
    
    try:
        auth_response = get_token(username, password, api_url)
        config['token'] = auth_response['access_token']
        config['user_id'] = auth_response['user_id']
        config['username'] = auth_response['username']
        save_config(config)
        return config
    except AuthenticationError as e:
        click.echo(f"Authentication failed: {str(e)}", err=True)
        raise click.Abort()

@click.group()
def cli():
    """Command Notes CLI - Save and retrieve terminal commands"""
    pass

@cli.command()
@click.option('--env', type=click.Choice(list(ENVIRONMENTS.keys())), default=DEFAULT_ENV,
              help='Environment to use (prod, prod_www, dev, dev_alt)')
def configure(env: str):
    """Configure CLI credentials and environment"""
    config = load_config()
    config['environment'] = env
    api_url, frontend_url = get_urls(config)
    
    click.echo(f"Configuring for environment: {env}")
    click.echo(f"API URL: {api_url}")
    click.echo(f"Frontend URL: {frontend_url}")
    
    config = refresh_authentication(config)
    click.echo(f"Configuration saved successfully for user {config['username']}!")

@cli.command()
def status():
    """Show current configuration status"""
    try:
        config = load_config()
        api_url, frontend_url = get_urls(config)
        
        if not config.get('token'):
            click.echo("Not authenticated. Please run 'configure' first.")
            return
        
        click.echo("Current Configuration:")
        click.echo(f"Environment: {config.get('environment', 'Not set')}")
        click.echo(f"API URL: {api_url}")
        click.echo(f"Frontend URL: {frontend_url}")
        click.echo(f"Username: {config.get('username', 'Not set')}")
        
        is_valid = validate_token(config['token'], api_url)
        click.echo(f"Token Status: {'Valid' if is_valid else 'Invalid'}")
        
        if is_valid:
            user_info = get_user_info(config['token'], api_url)
            click.echo(f"Authenticated as: {user_info['username']} (ID: {user_info['id']})")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

@cli.command()
@click.argument('name')
@click.option('--dry-run', is_flag=True, help='Show commands without executing them')
def deploy(name: str, dry_run: bool):
    """Execute a saved deployment script by name"""
    try:
        config = load_config()
        api_url, _ = get_urls(config)
        
        if not config.get('token'):
            config = refresh_authentication(config)
        
        # Get all notes
        response = requests.get(
            f"{api_url}/command_notes/",
            params={"user_id": config["user_id"]},
            headers={"Authorization": f"Bearer {config['token']}"}
        )
        response.raise_for_status()
        notes = response.json()
        # Find the note with matching name
        deployment_note = None
        for note in notes:
            if note['title'].lower() == name.lower():
                deployment_note = note
                break
        
        if not deployment_note:
            click.echo(f"No deployment script found with name: {name}")
            return
        
        # Show what we're about to do
        click.echo(f"\nFound deployment script: {deployment_note['title']}")
        click.echo(f"Description: {deployment_note['description']}")
        click.echo("\nCommands to execute:")
        for i, cmd in enumerate(deployment_note['commands'], 1):
            click.echo(f"{i}. {cmd}")
        
        if not dry_run:
            if not click.confirm('\nDo you want to execute these commands?'):
                return
            
            for i, cmd in enumerate(deployment_note['commands'], 1):
                click.echo(f"\nExecuting step {i}: {cmd}")
                try:
                    if cmd.startswith('sudo '):
                        sudo_password = click.prompt('Enter sudo password', hide_input=True)
                        cmd = f'echo {sudo_password} | sudo -S ' + cmd[5:]
                    
                    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                    if result.returncode == 0:
                        click.echo(click.style("✓ Success", fg="green"))
                        if result.stdout:
                            click.echo(result.stdout)
                    else:
                        click.echo(click.style("✗ Failed", fg="red"))
                        if result.stderr:
                            click.echo(result.stderr)
                        if not click.confirm('Command failed. Continue?'):
                            return
                except Exception as e:
                    click.echo(f"Error executing command: {str(e)}")
                    if not click.confirm('Continue despite error?'):
                        return
        else:
            click.echo("\nDry run - no commands were executed")
            
    except requests.exceptions.RequestException as e:
        click.echo(f"Error accessing API: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

if __name__ == '__main__':
    cli()