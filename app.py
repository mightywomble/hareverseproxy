# haproxy_web_app/app.py

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import subprocess
import logging
import re # Import regex for easier text manipulation
import ipaddress
import socket

# Get the directory of the current script (app.py)
# This ensures that Flask finds the templates and static folders relative to app.py's location,
# regardless of the working directory Gunicorn might be in.
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(basedir, 'templates'),
    static_folder=os.path.join(basedir, 'static')
)
app.secret_key = os.urandom(24)

# Configuration paths - CORRECTED PATH HERE
CONFIG_D_DIR = "/etc/haproxy/conf.d" # <--- CORRECTED
HAPROXY_CFG_PATH = "/etc/haproxy/haproxy.cfg"
FRONTEND_CFG_PATH = os.path.join(CONFIG_D_DIR, "00-frontend.cfg")

# --- Utility Functions ---

def run_command(command, check_output=True):
    """Executes a shell command and returns its output or status."""
    try:
        if check_output:
            result = subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
            return True, result.stdout.strip()
        else:
            subprocess.run(command, check=True, shell=True)
            return True, "Command executed successfully."
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {command}\nStdout: {e.stdout}\nStderr: {e.stderr}")
        return False, f"Command failed: {e.stderr.strip() or e.stdout.strip() or 'Unknown error'}"
    except FileNotFoundError:
        logging.error(f"Command not found: {command.split(' ')[0]}")
        return False, f"Error: Command '{command.split(' ')[0]}' not found. Is it in your PATH?"
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return False, f"An unexpected error occurred: {str(e)}"

def get_haproxy_status():
    """Checks the HAProxy service status."""
    success, output = run_command("sudo systemctl status haproxy", check_output=True)
    if success:
        if "active (running)" in output:
            return "running"
        elif "inactive (dead)" in output:
            return "stopped"
        else:
            return "unknown"
    return "error"

def get_config_files():
    """Lists .cfg files in config.d directory."""
    files = []
    try:
        for filename in os.listdir(CONFIG_D_DIR):
            if filename.endswith(".cfg") and os.path.isfile(os.path.join(CONFIG_D_DIR, filename)):
                files.append(filename)
        files.sort()
    except Exception as e:
        logging.error(f"Error listing config files: {e}")
    return files

def get_config_file_content(filename):
    """Reads the content of a specific config file."""
    file_path = os.path.join(CONFIG_D_DIR, filename)
    if not os.path.exists(file_path):
        return False, "File not found."
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return True, content
    except Exception as e:
        logging.error(f"Error reading file {filename}: {e}")
        return False, f"Error reading file: {str(e)}"

def update_frontend_cfg(service_name, service_url):
    """Adds acl and use_backend entries to 00-frontend.cfg in appropriate sections."""
    try:
        # Create the file if it doesn't exist, or read existing content
        if not os.path.exists(FRONTEND_CFG_PATH):
            # Provide a basic initial structure for a new frontend.cfg
            initial_content = """# --- Frontend for HTTP (port 80) - handles redirection ---
frontend http_redirect_frontend
    bind *:80
    mode http
    # Redirect all HTTP traffic to HTTPS for the same host
    redirect scheme https code 301 if !{ ssl_fc }

frontend https_frontend
    bind *:443 ssl crt /etc/haproxy/certs/cloudflare.pem alpn h2,http/1.1

    # ACLs to match hostnames

    # Use backends based on hostname

    # Default backend if no match
    default_backend default_backend
"""
            with open(FRONTEND_CFG_PATH, 'w') as f:
                f.write(initial_content)
            content = initial_content
        else:
            with open(FRONTEND_CFG_PATH, 'r') as f:
                content = f.read()

        acl_line = f"    acl host_{service_name} hdr(host) -i {service_url}"
        use_backend_line = f"    use_backend {service_name}_backend if host_{service_name}"

        # --- Insert ACL line ---
        # Regex to find the "ACLs to match hostnames" comment and the following lines
        acl_pattern = re.compile(r"(\s*# ACLs to match hostnames\s*\n)((\s*acl host_\S+ hdr\(host\).*?\n)*)", re.MULTILINE)

        # Check if ACL line already exists
        if acl_line.strip() not in [line.strip() for line in content.splitlines()]:
            match = acl_pattern.search(content)
            if match:
                # Insert after the existing ACLs (or directly after the comment if none)
                # Group 1 is the comment, Group 2 is existing ACLs
                insertion_point = match.end()
                content = content[:insertion_point] + acl_line + "\n" + content[insertion_point:]
            else:
                # Fallback: if marker not found, append to end of https_frontend block
                logging.warning("ACL insertion marker not found, appending ACL to end of file.")
                content += "\n" + acl_line + "\n" # Adding newline for clean append

        # --- Insert use_backend line ---
        # Regex to find the "Use backends based on hostname" comment and the following lines
        use_backend_pattern = re.compile(r"(\s*# Use backends based on hostname\s*\n)((\s*use_backend\s+.*?if\s+host_.*?\n)*)", re.MULTILINE)

        # Check if use_backend line already exists
        if use_backend_line.strip() not in [line.strip() for line in content.splitlines()]:
            match = use_backend_pattern.search(content)
            if match:
                # Insert after the existing use_backends (or directly after the comment if none)
                insertion_point = match.end()
                content = content[:insertion_point] + use_backend_line + "\n" + content[insertion_point:]
            else:
                # Fallback: if marker not found, try to insert before default_backend
                default_backend_pattern = re.compile(r"(\s*default_backend\s+\S+)", re.MULTILINE)
                match = default_backend_pattern.search(content)
                if match:
                    insertion_point = match.start() # Insert just before default_backend
                    content = content[:insertion_point] + use_backend_line + "\n\n" + content[insertion_point:]
                else:
                    logging.warning("Use_backend insertion marker and default_backend not found, appending to end of file.")
                    content += "\n" + use_backend_line + "\n" # Adding newline for clean append

        # Write the modified content back to the file
        with open(FRONTEND_CFG_PATH, 'w') as f:
            f.write(content)

        return True, "00-frontend.cfg updated successfully."
    except Exception as e:
        logging.error(f"Error updating 00-frontend.cfg: {e}")
        return False, f"Error updating 00-frontend.cfg: {str(e)}"

# --- HAProxy Configuration Parser for Network Map ---

def parse_haproxy_configs():
    """Parse HAProxy configuration files to extract network topology data."""
    topology = {
        'haproxy_server': {
            'id': 'haproxy_hub',
            'type': 'haproxy',
            'name': 'HAProxy Server',
            'status': get_haproxy_status()
        },
        'frontends': [],
        'backends': [],
        'connections': [],
        'external_clients': []
    }
    
    try:
        # Parse main haproxy.cfg
        if os.path.exists(HAPROXY_CFG_PATH):
            with open(HAPROXY_CFG_PATH, 'r') as f:
                main_config = f.read()
                parse_config_content(main_config, topology, 'haproxy.cfg')
        
        # Parse config.d files
        config_files = get_config_files()
        for filename in config_files:
            success, content = get_config_file_content(filename)
            if success:
                parse_config_content(content, topology, filename)
                
        # Add external client nodes
        add_external_clients(topology)
        
        # Generate connections between components
        generate_connections(topology)
        
        return topology
        
    except Exception as e:
        logging.error(f"Error parsing HAProxy configs: {e}")
        return {
            'error': f"Error parsing configurations: {str(e)}",
            'haproxy_server': topology['haproxy_server'],
            'frontends': [],
            'backends': [],
            'connections': [],
            'external_clients': []
        }

def parse_config_content(content, topology, filename):
    """Parse individual config file content."""
    lines = content.split('\n')
    current_section = None
    current_config = {}
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # Frontend section
        if line.startswith('frontend '):
            if current_section and current_config:
                finalize_section(current_section, current_config, topology, filename)
            current_section = 'frontend'
            current_config = {
                'name': line.split()[1],
                'binds': [],
                'acls': [],
                'use_backends': [],
                'default_backend': None,
                'filename': filename
            }
            
        # Backend section
        elif line.startswith('backend '):
            if current_section and current_config:
                finalize_section(current_section, current_config, topology, filename)
            current_section = 'backend'
            current_config = {
                'name': line.split()[1],
                'servers': [],
                'mode': 'http',
                'balance': 'roundrobin',
                'filename': filename
            }
            
        # Parse frontend/backend directives
        elif current_section:
            if line.startswith('bind '):
                bind_info = parse_bind_directive(line)
                if bind_info:
                    current_config['binds'].append(bind_info)
                    
            elif line.startswith('acl '):
                acl_info = parse_acl_directive(line)
                if acl_info:
                    current_config['acls'].append(acl_info)
                    
            elif line.startswith('use_backend '):
                backend_info = parse_use_backend_directive(line)
                if backend_info:
                    current_config['use_backends'].append(backend_info)
                    
            elif line.startswith('default_backend '):
                current_config['default_backend'] = line.split()[1]
                
            elif line.startswith('server '):
                server_info = parse_server_directive(line)
                if server_info:
                    current_config['servers'].append(server_info)
                    
            elif line.startswith('mode '):
                current_config['mode'] = line.split()[1]
                
            elif line.startswith('balance '):
                current_config['balance'] = line.split()[1]
    
    # Don't forget the last section
    if current_section and current_config:
        finalize_section(current_section, current_config, topology, filename)

def parse_bind_directive(line):
    """Parse bind directive to extract IP and port."""
    parts = line.split()
    if len(parts) < 2:
        return None
        
    bind_addr = parts[1]
    ssl_enabled = 'ssl' in line
    
    # Parse address:port
    if ':' in bind_addr:
        if bind_addr.startswith('*:'):
            ip = '0.0.0.0'
            port = bind_addr.split(':')[1]
        else:
            ip, port = bind_addr.split(':', 1)
    else:
        ip = bind_addr
        port = '80' if not ssl_enabled else '443'
    
    return {
        'ip': ip,
        'port': int(port),
        'ssl': ssl_enabled,
        'protocol': 'HTTPS' if ssl_enabled else 'HTTP'
    }

def parse_acl_directive(line):
    """Parse ACL directive."""
    parts = line.split()
    if len(parts) < 4:
        return None
    
    return {
        'name': parts[1],
        'matcher': ' '.join(parts[2:]),
        'type': 'hostname' if 'hdr(host)' in line else 'other'
    }

def parse_use_backend_directive(line):
    """Parse use_backend directive."""
    parts = line.split()
    if len(parts) < 2:
        return None
    
    backend_name = parts[1]
    condition = ' '.join(parts[3:]) if len(parts) > 3 else None
    
    return {
        'backend': backend_name,
        'condition': condition
    }

def parse_server_directive(line):
    """Parse server directive to extract backend server info."""
    parts = line.split()
    if len(parts) < 3:
        return None
    
    server_name = parts[1]
    server_addr = parts[2]
    
    # Parse IP:port
    if ':' in server_addr:
        ip, port = server_addr.split(':', 1)
    else:
        ip = server_addr
        port = '80'
    
    # Check for SSL
    ssl_enabled = 'ssl' in line
    
    # Check for health checks
    health_check = 'check' in line
    
    return {
        'name': server_name,
        'ip': ip,
        'port': int(port),
        'ssl': ssl_enabled,
        'health_check': health_check,
        'status': check_server_status(ip, int(port))
    }

def check_server_status(ip, port):
    """Check if a server is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip, port))
        sock.close()
        return 'healthy' if result == 0 else 'unreachable'
    except:
        return 'unknown'

def finalize_section(section_type, config, topology, filename):
    """Add completed section to topology."""
    if section_type == 'frontend':
        # Generate unique ID
        config['id'] = f"frontend_{config['name']}"
        config['type'] = 'frontend'
        topology['frontends'].append(config)
        
    elif section_type == 'backend':
        # Generate unique ID
        config['id'] = f"backend_{config['name']}"
        config['type'] = 'backend'
        topology['backends'].append(config)

def add_external_clients(topology):
    """Add external client nodes based on frontend configurations."""
    client_types = set()
    
    for frontend in topology['frontends']:
        for bind in frontend['binds']:
            if bind['port'] == 80:
                client_types.add('http_clients')
            elif bind['port'] == 443:
                client_types.add('https_clients')
            else:
                client_types.add(f'port_{bind["port"]}_clients')
    
    for client_type in client_types:
        if client_type == 'http_clients':
            name = 'HTTP Clients'
            port = 80
            protocol = 'HTTP'
        elif client_type == 'https_clients':
            name = 'HTTPS Clients'
            port = 443
            protocol = 'HTTPS'
        else:
            port_num = client_type.split('_')[1]
            name = f'Port {port_num} Clients'
            port = int(port_num)
            protocol = 'TCP'
        
        topology['external_clients'].append({
            'id': client_type,
            'type': 'external_client',
            'name': name,
            'port': port,
            'protocol': protocol
        })

def generate_connections(topology):
    """Generate connections between nodes."""
    connections = []
    
    # Connections from external clients to frontends
    for client in topology['external_clients']:
        for frontend in topology['frontends']:
            for bind in frontend['binds']:
                if bind['port'] == client['port']:
                    connections.append({
                        'id': f"conn_{client['id']}_to_{frontend['id']}",
                        'source': client['id'],
                        'target': frontend['id'],
                        'type': 'incoming',
                        'protocol': client['protocol'],
                        'port': client['port']
                    })
    
    # Connections from frontends to backends
    for frontend in topology['frontends']:
        # Direct use_backend connections
        for use_backend in frontend['use_backends']:
            backend_name = use_backend['backend']
            backend = next((b for b in topology['backends'] if b['name'] == backend_name), None)
            if backend:
                connections.append({
                    'id': f"conn_{frontend['id']}_to_{backend['id']}",
                    'source': frontend['id'],
                    'target': backend['id'],
                    'type': 'routing',
                    'condition': use_backend.get('condition'),
                    'protocol': 'HTTP/HTTPS'
                })
        
        # Default backend connection
        if frontend['default_backend']:
            backend = next((b for b in topology['backends'] if b['name'] == frontend['default_backend']), None)
            if backend:
                connections.append({
                    'id': f"conn_{frontend['id']}_to_{backend['id']}_default",
                    'source': frontend['id'],
                    'target': backend['id'],
                    'type': 'default_routing',
                    'protocol': 'HTTP/HTTPS'
                })
    
    # Connections from backends to servers
    for backend in topology['backends']:
        for server in backend['servers']:
            server_id = f"server_{backend['name']}_{server['name']}"
            connections.append({
                'id': f"conn_{backend['id']}_to_{server_id}",
                'source': backend['id'],
                'target': server_id,
                'type': 'backend_server',
                'protocol': 'HTTPS' if server['ssl'] else 'HTTP',
                'port': server['port'],
                'server_status': server['status']
            })
    
    topology['connections'] = connections

# --- Routes ---

@app.route('/')
def index():
    status = get_haproxy_status()
    return render_template('index.html', haproxy_status=status)

@app.route('/api/haproxy_status')
def api_haproxy_status():
    status = get_haproxy_status()
    return jsonify(status=status)

@app.route('/api/haproxy_action', methods=['POST'])
def api_haproxy_action():
    action = request.json.get('action')
    command_map = {
        'start': 'sudo systemctl start haproxy',
        'stop': 'sudo systemctl stop haproxy',
        'restart': 'sudo systemctl restart haproxy',
        'test': f'sudo haproxy -c -f {HAPROXY_CFG_PATH}'
    }

    command = command_map.get(action)
    if not command:
        return jsonify(success=False, message="Invalid action"), 400

    success, message = run_command(command, check_output=True)
    return jsonify(success=success, message=message)

@app.route('/config_d')
def config_d_list():
    files = get_config_files()
    return render_template('config_d.html', config_files=files)

@app.route('/config_d/add', methods=['GET', 'POST'])
def add_config_d():
    if request.method == 'POST':
        # This branch handles manual file addition
        filename = request.form.get('filename')
        content = request.form.get('content')
        if not filename or not content:
            return jsonify(success=False, message="Filename and content are required."), 400

        file_path = os.path.join(CONFIG_D_DIR, filename)
        if os.path.exists(file_path):
            return jsonify(success=False, message=f"File '{filename}' already exists."), 409

        try:
            with open(file_path, 'w') as f:
                f.write(content)
            return jsonify(success=True, message=f"File '{filename}' created successfully.")
        except Exception as e:
            return jsonify(success=False, message=f"Error creating file: {str(e)}"), 500
    # For GET requests, render the page with options for wizard/manual
    return render_template('edit_config_d.html', new_file=True, content="", filename="")

@app.route('/api/config_d/wizard', methods=['POST'])
def wizard_add_config():
    data = request.json
    service_name = data.get('service_name')
    service_ip = data.get('service_ip')
    service_port = data.get('service_port')
    service_url = data.get('service_url')
    is_https = data.get('is_https') # This will be boolean

    if not all([service_name, service_ip, service_port, service_url]):
        return jsonify(success=False, message="All wizard fields are required."), 400

    # Sanitize service_name for filename and internal use
    # Replace non-alphanumeric with underscore, ensure it starts with a letter or underscore
    sanitized_service_name = re.sub(r'[^a-zA-Z0-9_]', '_', service_name)
    if not sanitized_service_name or not sanitized_service_name[0].isalpha() and not sanitized_service_name[0] == '_':
        sanitized_service_name = "service_" + sanitized_service_name.lstrip('_')
    
    # Generate backend config
    backend_filename = f"10-{sanitized_service_name}_backend.cfg"
    backend_content = f"""backend {sanitized_service_name}_backend
    mode http
    balance roundrobin
    option forwardfor
    http-reuse safe
    server {sanitized_service_name}_server {service_ip}:{service_port} check inter 5s fall 3 rise 2"""

    if is_https:
        backend_content += " ssl verify none"
    
    backend_content += """
    timeout connect 10s
    timeout server 30s
    retries 4
"""

    backend_file_path = os.path.join(CONFIG_D_DIR, backend_filename)

    # Write backend file
    try:
        with open(backend_file_path, 'w') as f:
            f.write(backend_content)
    except Exception as e:
        return jsonify(success=False, message=f"Error creating backend file '{backend_filename}': {str(e)}"), 500

    # Update 00-frontend.cfg
    success, message = update_frontend_cfg(sanitized_service_name, service_url)
    if not success:
        # Consider rolling back backend file creation if frontend update fails, or just log
        logging.warning(f"Frontend update failed after backend file creation: {message}")
        return jsonify(success=False, message=f"Backend created, but frontend update failed: {message}"), 500

    # Get the updated frontend content to display
    frontend_cfg_success, frontend_cfg_display_content = get_config_file_content("00-frontend.cfg")
    if not frontend_cfg_success:
        frontend_cfg_display_content = "Could not retrieve updated 00-frontend.cfg content."


    return jsonify(
        success=True,
        message=f"Backend '{backend_filename}' and 00-frontend.cfg updated successfully.",
        frontend_cfg_path=FRONTEND_CFG_PATH, # Pass path for display on frontend
        frontend_cfg_content=frontend_cfg_display_content # Pass content for display
    )


@app.route('/config_d/edit/<filename>', methods=['GET', 'POST'])
def edit_config_d(filename):
    file_path = os.path.join(CONFIG_D_DIR, filename)
    if not os.path.exists(file_path):
        return "File not found", 404

    if request.method == 'POST':
        content = request.form.get('content')
        if content is None:
            return jsonify(success=False, message="Content is required."), 400
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            return jsonify(success=True, message=f"File '{filename}' updated successfully.")
        except Exception as e:
            return jsonify(success=False, message=f"Error updating file: {str(e)}"), 500
    else:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            return render_template('edit_config_d.html', filename=filename, content=content, new_file=False)
        except Exception as e:
            return f"Error reading file: {str(e)}", 500

@app.route('/api/config_d/delete/<filename>', methods=['DELETE'])
def delete_config_d(filename):
    file_path = os.path.join(CONFIG_D_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify(success=False, message="File not found."), 404
    try:
        os.remove(file_path)
        # TODO: Potentially remove associated ACL/use_backend lines from 00-frontend.cfg
        return jsonify(success=True, message=f"File '{filename}' deleted successfully.")
    except Exception as e:
        return jsonify(success=False, message=f"Error deleting file: {str(e)}"), 500

@app.route('/api/config_d/content/<filename>')
def api_config_d_content(filename):
    success, content = get_config_file_content(filename)
    if success:
        return jsonify(success=True, content=content)
    else:
        return jsonify(success=False, message=content), 404 # Use 404 if file not found


@app.route('/map')
def network_map():
    """Display the network topology map."""
    return render_template('network_map.html')

@app.route('/api/network_topology')
def api_network_topology():
    """API endpoint to get network topology data."""
    topology = parse_haproxy_configs()
    return jsonify(topology)

@app.route('/api/server_status/<server_ip>/<int:server_port>')
def api_server_status(server_ip, server_port):
    """Check individual server status."""
    status = check_server_status(server_ip, server_port)
    return jsonify({
        'ip': server_ip,
        'port': server_port,
        'status': status
    })

@app.route('/haproxy_cfg', methods=['GET', 'POST'])
def haproxy_cfg():
    if request.method == 'POST':
        content = request.form.get('content')
        if content is None:
            return jsonify(success=False, message="Content is required."), 400
        try:
            with open(HAPROXY_CFG_PATH, 'w') as f:
                f.write(content)
            return jsonify(success=True, message="haproxy.cfg updated successfully.")
        except Exception as e:
            return jsonify(success=False, message=f"Error updating haproxy.cfg: {str(e)}"), 500
    else:
        try:
            with open(HAPROXY_CFG_PATH, 'r') as f:
                content = f.read()
            return render_template('haproxy_cfg.html', content=content)
        except Exception as e:
            return f"Error reading haproxy.cfg: {str(e)}", 500

# --- Error Handling ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    # This part runs only when app.py is executed directly, not via gunicorn
    app.run(debug=True, host='0.0.0.0', port=5000)
