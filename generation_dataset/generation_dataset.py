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

RUNOS_IP = '172.20.6.2'
RUNOS_PORT = '8000'
RUNOS_FLOW_STATS = f'http://{RUNOS_IP}:{RUNOS_PORT}/stats/flow'
RUNOS_SWITCH_STATS = f'http://{RUNOS_IP}:{RUNOS_PORT}/stats/switch'
RUNOS_HOST_STATS = f'http://{RUNOS_IP}:{RUNOS_PORT}/stats/host'
RUNOS_CLI_API = f'http://{RUNOS_IP}:{RUNOS_PORT}/cli'

def generate_random_mac():
    """Generates a random MAC address"""
    return "00:%02x:%02x:%02x:%02x:%02x" % (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    )

def generate_random_ip():
    """Generates a random IP address"""
    return f"{randint(1,255)}.{randint(0,255)}.{randint(0,255)}.{randint(0,255)}"

def run_cmd(host, cmd):
    """Executes the command on the host without unnecessary output"""
    return host.cmd(cmd)

def generate_traffic(net, src_host, dst_host, duration=5):
    """Generates normal traffic"""
    
    info(
        f"*** Generating traffic between {src_host.name} and {dst_host.name} for {duration} seconds\n")
    
    src_mac = src_host.cmd(f"cat /sys/class/net/{src_host.defaultIntf()}/address").strip()
    packet_size = random.randint(64, 1500)
    packet_rate = random.randint(10, 1000)
    total_packets = duration * packet_rate
    total_bytes = total_packets * packet_size
    cmd = (f"hping3 {dst_host.IP()} -c {total_packets} "
           f"-i {1/packet_rate} -d {packet_size} --fast")
    run_cmd(src_host, f"{cmd} >/dev/null 2>&1 &")

    time.sleep(duration + 1)
    
    return {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'src_host': src_host.name,
        'src_ip': src_host.IP(),
        'src_mac': src_mac,
        'dst_host': dst_host.name,
        'dst_ip': dst_host.IP(),
        'duration': duration,
        'Interval': f"0.0-{duration}",
        'Transfer': f"{(total_bytes/1e6):.2f} MB",
        'Bandwidth': f"{(total_bytes*8/duration/1e6):.2f} Mbits/sec",
        'is_attack': 0,
        'attack_type': 'normal',
        'attackers_count': 0,
        'packet_frequency': f"1 packet every {1/packet_rate:.4f} seconds",
        'bytecount': total_bytes,
        'pktcount': total_packets,
        'pktperflow': total_packets,
        'byteperflow': total_bytes,
        'pktrate': packet_rate
    }

def run_advanced_attack(attacker, target_ip, attack_type, duration, packet_size, packet_rate):
    """Universal function for performing attacks: syn, udp, icmp, http"""
    packet_size = randint(64, 1500)
    packet_rate = randint(10000, 50000)
    if attack_type == 'syn':
        cmd = f"timeout {duration} hping3 {target_ip} -S --flood --rand-source --data {packet_size} --count {packet_rate*duration}"
    elif attack_type == 'udp':
        cmd = f"timeout {duration} hping3 {target_ip} -2 --flood --rand-source --data {packet_size} --count {packet_rate*duration}"
    elif attack_type == 'icmp':
        cmd = f"timeout {duration} hping3 {target_ip} -1 --flood --rand-source --data {packet_size} --count {packet_rate*duration}"
    elif attack_type == 'http':
        random_url = f"http://{target_ip}/{'x'*randint(10,100)}?{'y'*randint(10,50)}"
        cmd = f"timeout {duration} ab -n {packet_rate*duration} -c {randint(50,200)} {random_url}"
    
    run_cmd(attacker, cmd)


def generate_ddos_attack(net, duration=10, attackers_count=5):
    """Generates a DDoS attack with a large number of packets"""
    attackers = sample(net.hosts, min(attackers_count, len(net.hosts)))
    attack_type = random.choice(['syn', 'udp', 'icmp', 'http'])
    
    info(f"*** DDoS attack with {attackers_count} attackers\n")
    info(f"*** Attack type: {attack_type} (using random MAC/IP)\n")

    processes = []
    target_ips = [generate_random_ip() for _ in range(min(10, len(net.hosts)- len(attackers)))]
    current_target = [None] * len(attackers)
    current_target_name = [None] * len(attackers)
    packet_size = [None] * len(attackers)
    packet_rate = [None] * len(attackers)
    total_packets = [None] * len(attackers)
    total_bytes = [None] * len(attackers)
    for i in range(len(attackers)):
        attacker = attackers[i]
        attacker_mac = generate_random_mac()
        run_cmd(attacker, f'ifconfig {attacker.defaultIntf()} hw ether {attacker_mac}')
        
        current_target[i] = choice(target_ips)
        current_target_name[i] = 'h' + f'{random.randint(len(net.hosts) + 1, 20000)}'
        packet_size[i] = random.choice([64, 128, 512, 1024, 1500])
        packet_rate[i] = random.randint(5000, 20000)
        total_packets[i] = duration * packet_rate[i]
        total_bytes[i] = total_packets[i] * packet_size[i]
        
        
        p = Process(target=run_advanced_attack, 
                   args=(attacker, current_target[i], attack_type, duration, packet_size[i], packet_rate[i]))
        p.start()
        processes.append(p)

    time.sleep(duration)
    
    for attacker in attackers:
        run_cmd(attacker, "killall -9 hping3 ab >/dev/null 2>&1 || true")
    
    attack_stats = []
    for i in range(len(attackers)):
        attacker = attackers[i]
        attack_stats.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'src_host': attacker.name,
            'src_ip': attacker.IP(),
            'src_mac': attacker.cmd(f"cat /sys/class/net/{attacker.defaultIntf()}/address").strip(),
            'dst_host': current_target_name[i],
            'dst_ip': current_target[i],
            'duration': duration,
            'Interval': f"0.0-{duration}",
            'Transfer': f"{(total_bytes[i]/1e6):.2f} MB",
            'Bandwidth': f"{(total_bytes[i]*8/duration/1e6):.2f} Mbits/sec",
            'is_attack': 1,
            'attack_type': f'ddos-{attack_type}',
            'attackers_count': len(attackers),
            'packet_frequency': f"1 packet every {1/packet_rate[i]:.6f} seconds",
            'bytecount': total_bytes[i],
            'pktcount': total_packets[i],
            'pktperflow': total_packets[i] / len(attackers),
            'byteperflow': total_bytes[i] / len(attackers),
            'pktrate': packet_rate[i]
        })
    
    return attack_stats

def capture_traffic_stats(net, filename='traffic.csv', test_duration=30, attack_prob=0.3):
    """Generates a dataset with normal traffic and attacks, saves statistics in CSV"""

    fieldnames = [
        'timestamp', 'src_host', 'src_ip', 'src_mac',
        'dst_host', 'dst_ip', 'duration', 'Interval', 
        'Transfer', 'Bandwidth', 'is_attack', 'attack_type',
        'attackers_count', 'packet_frequency', 'bytecount', 
        'pktcount', 'pktperflow', 'byteperflow', 'pktrate'
    ]

    with open(filename, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()

        start_time = time.time()
        while time.time() - start_time < test_duration:
            if random.random() < attack_prob and len(net.hosts) > 2:
                target = choice(net.hosts)
                attack_stats = generate_ddos_attack(
                    net, 
                    duration=random.randint(5, 15),
                    attackers_count=random.randint(1, min(10, len(net.hosts)-1))
                )
                for stats in attack_stats:
                    writer.writerow(stats)
            else:
                src, dst = sample(net.hosts, 2)
                stats = generate_traffic(net, src, dst, duration=random.randint(1, 5))
                writer.writerow(stats)
            
            time.sleep(1)

def create_custom_topo(hosts=2, topo_type="linear"):
    """Creating a network topology"""
    cleanup()
    runos_controller = RemoteController('c0', ip=RUNOS_IP, port=6653, protocols='OpenFlow13', connection_timeout=20)
    net = Mininet(controller=runos_controller, link=TCLink)
    net.addController(runos_controller)

    host_list = []
    switch_list = []
    
    for i in range(1, hosts+1):
        host = net.addHost(f'h{i}')
        host_list.append(host)
        
    for i in range(1, hosts+1):
        switch = net.addSwitch(f's{i}', protocols='OpenFlow13', listenPort=6666 + i )
        switch_list.append(switch)

    if topo_type == "linear":
        for i in range(hosts):
            net.addLink(host_list[i], switch_list[i])
            if i > 0:
                net.addLink(switch_list[i-1], switch_list[i])
    elif topo_type == "star":
        center_switch = net.addSwitch('s0', protocols='OpenFlow13', listenPort=6665)
        for i in range(hosts):
            host = host_list[i]
            switch = switch_list[i] if i < len(switch_list) else None
            net.addLink(host, switch) 
            net.addLink(switch, center_switch)
        switch_list.insert(0, center_switch)
    elif topo_type == "ring":
        for i in range(hosts):
            net.addLink(host_list[i], switch_list[i])
            next_idx = (i + 1) % hosts
            net.addLink(switch_list[i], switch_list[next_idx])
    else:
        raise ValueError(f"Unknown topology type: {topo_type}")

    net.start()
    for switch in net.switches:
        switch.cmd(f'ovs-vsctl set bridge {switch.name} protocols=OpenFlow13')
        switch.cmd(f'ovs-vsctl set bridge {switch.name} stp_enable=false')        
        switch.cmd(f'ovs-vsctl set controller {switch.name} connection_mode=out-of-band')
        switch.cmd(f'ovs-vsctl set-controller {switch.name} tcp:{RUNOS_IP}:6653')   
        switch.cmd(f'ovs-ofctl -O OpenFlow13 mod-port {switch.name} {switch.ports[0]} up')
        switch.cmd(f'ovs-ofctl -O OpenFlow13 role-request {switch.name} master') 

    time.sleep(10)  # Даем время RUNOS обнаружить топологию
    for switch in net.switches:
        info(f"*** Checking {switch.name} connection...\n")
        controllers = switch.cmd('ovs-vsctl get-controller %s' % switch.name)
        if RUNOS_IP not in controllers:
            info(f"*** Warning: {switch.name} is not connected to controller!\n")
    
    return net

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Mininet Custom Topology with Traffic Generator')
    parser.add_argument('--hosts', type=int, default=4, help='Number of hosts')
    parser.add_argument('--topo', type=str, default="linear",
                        choices=["linear", "star", "ring"], help='Topology type')
    parser.add_argument('--duration', type=int, default=300, help='Test duration in seconds')
    parser.add_argument('--output', type=str, default='traffic_dataset.csv',
                        help='Output CSV file for statistics')
    parser.add_argument('--attack_prob', type=float, default=0.3,
                       help='Probability of attack between two hosts')
    args = parser.parse_args()

    cleanup()
    setLogLevel('info')
    try:
        net = create_custom_topo(args.hosts, args.topo)
        capture_traffic_stats(net, args.output, args.duration, args.attack_prob)
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if 'net' in locals():
            net.stop()