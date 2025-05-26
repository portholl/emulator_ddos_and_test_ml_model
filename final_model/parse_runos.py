from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from multiprocessing import Process
import csv
import argparse
import time
from datetime import datetime
from random import randint, choice, sample, uniform
import random
from mininet.clean import cleanup
import requests
import json
import re

RUNOS_IP = '172.20.6.2'
RUNOS_PORT = '8000'
RUNOS_FLOW_STATS = f'http://{RUNOS_IP}:{RUNOS_PORT}/stats/flow'
RUNOS_SWITCH_STATS = f'http://{RUNOS_IP}:{RUNOS_PORT}/stats/switch'
RUNOS_HOST_STATS = f'http://{RUNOS_IP}:{RUNOS_PORT}/stats/host'
RUNOS_CLI_API = f'http://{RUNOS_IP}:{RUNOS_PORT}/cli'

def parse_show_info(text):
    """Parses the output of the 'show info' command"""
    result = {}
    
    patterns = {
        'switches': r'Number of switches:\s*(\d+)',
        'rx_packets': r'RX OpenFlow packets:\s*(\d+)',
        'tx_packets': r'TX OpenFlow packets:\s*(\d+)',
        'packet_in': r'Packet-In packets:\s*(\d+)',
        'uptime': r'RUNOS uptime\(sec\):\s*(\d+)',
        'start_time': r'RUNOS start time:\s*(.+)'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            result[key] = match.group(1).strip()
    
    for key in ['switches', 'rx_packets', 'tx_packets', 'packet_in', 'uptime']:
        if key in result:
            result[key] = int(result[key])
            
    return result

def parse_switch_list(text):
    """Parses the output of the 'switch list' command"""
    switches = []
    lines = text.split('\n')
    
    for line in lines[2:]:
        if not line.strip():
            continue
            
        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) >= 3:
            switches.append({
                'dpid': parts[0],
                'hardware': parts[1],
                'description': parts[2]
            })
    
    return switches

def parse_connection_list(text):
    """Parses the output of the 'connection list' command"""
    connections = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('DPID') or line.startswith('----'):
            continue
            
        parts = re.split(r'\s{2,}', line)
        if len(parts) >= 8:
            try:
                connection = {
                    'dpid': parts[0].strip(),
                    'status': parts[1].strip(),
                    'peer': parts[2].strip(),
                    'uptime': int(parts[3].strip()) if parts[3].strip().isdigit() else 0,
                    'rx': int(parts[4].strip()) if parts[4].strip().isdigit() else 0,
                    'tx': int(parts[5].strip()) if parts[5].strip().isdigit() else 0,
                    'packet_in': int(parts[6].strip()) if parts[6].strip().isdigit() else 0,
                    'start_time': parts[7].strip()
                }
                connections.append(connection)
            except (ValueError, IndexError) as e:
                info(f"*** Error parsing connection line '{line}': {e}\n")
                continue
    
    return connections

def get_runos_stats():
    """Collects statistics from the RUNOS controller"""
    stats = {
        'controller_info': {},
        'connections': [],
        'switches': []
    }
    
    try:
        # show info
        show_info_response = requests.get(f'http://{RUNOS_IP}:{RUNOS_PORT}/cli/show_info')
        if show_info_response.status_code == 200:
            stats['controller_info'] = parse_show_info(show_info_response.text)
        
        # switch list
        switch_list_response = requests.get(f'{RUNOS_CLI_API}/switch_list', timeout=5)
        if switch_list_response.status_code == 200:
            stats['switches'] = parse_switch_list(switch_list_response.text)
        
        # connection list
        conn_list_response = requests.get(f'{RUNOS_CLI_API}/connection_list', timeout=5)
        if conn_list_response.status_code == 200:
            stats['connections'] = parse_connection_list(conn_list_response.text)
            
            
    except Exception as e:
        info(f"*** Error getting CLI stats: {e}\n")
    
    return stats
def calculate_metrics(stats):
    """Calculates metrics based on statistics"""
    metrics = {
        'controller_uptime': 0,
        'controller_switches': 0,
        'total_rx_packets': 0,
        'total_tx_packets': 0,
        'total_packet_in': 0,
        'active_connections': 0,
        'total_links': 0,
        'avg_rx_rate': 0,
        'avg_tx_rate': 0
    }
    
    if 'controller_info' in stats:
        ci = stats['controller_info']
        metrics.update({
            'controller_uptime': stats.get('controller_info', {}).get('uptime', 0),
            'controller_switches': stats.get('controller_info', {}).get('switches', 0),
            'total_rx_packets': stats.get('controller_info', {}).get('rx_packets', 0),
            'total_tx_packets': stats.get('controller_info', {}).get('tx_packets', 0),
            'total_packet_in': stats.get('controller_info', {}).get('packet_in', 0),
            'avg_rx_rate': stats.get('controller_info', {}).get('rx_rate', 0),
            'avg_tx_rate': stats.get('controller_info', {}).get('tx_rate', 0)
        })
        
    if 'connections' in stats:
        metrics['active_connections'] = len([c for c in stats.get('connections', []) if c.get('status') == 'UP'])
    
    return metrics