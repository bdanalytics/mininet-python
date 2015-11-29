#!/usr/bin/env python

from pprint import pprint
from bwstats import BandwidthStats
from topo import Topology
import flood
import os
import sys

'''
Useful CoreSwitch class functions/properties:

    CoreSwitch.name - the name of the switch (eg, 's101')
    CoreSwitch.dpid - the dpid of the switch (eg, 101)
    CoreSwitch.vlans - list of pre-assigned vlans for the switch to handle


Useful EdgeSwitch class functions/properties:

    EdgeSwitch.name - the name of the switch (eg, 's101')
    EdgeSwitch.dpid - the dpid of the switch (eg, 101)
    EdgeSwitch.neighbors - list of hosts's names (eg, 'h6') attached to
                           the switch


Useful Host class functions/properties:

    Host.name - the name of the host (eg, 'h6')
    Host.eth - the MAC address of the host
    Host.switch - the switch to which the host is connected
    Host.vlans - a list of vlans with which the host is associated


Useful Topology class functions/properties:

    Topology.hosts - a dictionary of Host objects keyed on host name
    Topology.switches - a list of switch names
    Topology.coreSwitches - dictionary of CoreSwitch objects keyed on
                        switch name
    Topology.edgeSwitches - dictionary of EdgeSwitch objects keyed on
                        switch name
    Topology.vlans - dictionary of vlan members, keyed on the vlan id (an integer)
    Topology.ports[sw][inNode] - returns the port number on switch sw connected to
                             the adjacent node inNode, if inNode is a node name
                             (ie, switch or host).  If inNode is a number, returns
                             the node or switch name on that port on switch sw.
    Topology.getVlanCore(vlanId) - returns the core switch pre-assigned for the
                               vlan vlanId
    Topology.dpidToName(dpid) - returns the switch name associated with the
                                specified dpid
'''

class AdaptivePolicy(object):
    def __init__(self, topo, bwstats, logger):
        self.topo = topo
        self.bwstats = bwstats
        self.logger = logger
        self.assignments = {}
        self.utilization = {}
        default = topo.coreSwitches.keys()[0]
        for host in topo.hosts.keys():
            self.assignments[host] = default
        self._routingTable = self.build(self.topo)

    @property
    def routingTable(self):
        # rebuild with updated bandwidth stats
        self.redistribute()
        return self.build(self.topo)

    def minUtilization(self):
        # ASSIGNMENT 4:
        # This function should return the core switch that
        # is least utilized.  We will use this to greedily
        # assign hosts to core switches based on the amount
        # of traffic they are receiving and balance load
        # on the core switches.

        # Use the dictionary self.utilization
        # (key = switch name, value = utilization in bytes)
        # to find the least utilized switch.

        # [REPLACE WITH YOUR CODE]
        pPfx = "BBI:AdaptivePolicy:minUtilization:"
        print pPfx + "self.utilization:"
        pprint(self.utilization)
        
        utilizationTpls = sorted([(self.utilization[switch], switch) for switch in self.utilization.keys()])
        print pPfx + "utilizationTpls:"
        pprint(utilizationTpls)

        return utilizationTpls[0][1]

        # [DEFAULT CODE]
        #return self.utilization.keys()[0]

    def redistribute(self):
        # we're installing flows by destination, so sort by received
        stats = []
        for host in self.bwstats.hostBw.keys():
            stats.append((self.bwstats.hostBw[host]['in'], host))

        # sort largest to smallest
        stats.sort(reverse=True)

        # reset utilization
        for core in self.topo.coreSwitches.keys():
            self.utilization[core] = 0

        for stat in stats:
            host = stat[1]

            # greedily assign hosts to least utilized
            core = self.minUtilization()
            self.assignments[host] = core
            self.utilization[core] += stat[0]

        self.logger.info(self.utilization)
        self.logger.info(self.assignments)

    def build(self, topo):
        routingTable = {}

        # assign core-edge downward
        for core in topo.coreSwitches.values():
            routingTable[core.dpid] = []
            for h in topo.hosts.values():
                outport = topo.ports[core.name][h.switch]
                routingTable[core.dpid].append({
                    'eth_dst' : h.eth,
                    'output' : [outport],
                    'priority' : 2,
                    'type' : 'dst'
                })

        for edge in topo.edgeSwitches.values():
            routingTable[edge.dpid] = []
            for h in topo.hosts.values():
                # don't send neighbors up to core
                if h.name in edge.neighbors:
                    outport = topo.ports[edge.name][h.name]
                else:
                    # send to core
                    core = self.assignments[h.name]
                    outport = topo.ports[edge.name][core]

                routingTable[edge.dpid].append({
                    'eth_dst' : h.eth,
                    'output' : [outport],
                    'priority' : 2,
                    'type' : 'dst'
                })

        return flood.add_arpflood(routingTable, topo)

class StaticPolicy(object):
    def __init__(self, topo):
        self.routingTable = self.build(topo)

    def build(self, topo):
        routingTable = {}

        # core switches: for a given host destination, send packet
        # to the host's edge switch ("downward")
        for core in topo.coreSwitches.values():
            routingTable[core.dpid] = []
            for h in topo.hosts.values():
                outport = topo.ports[core.name][h.switch]
                routingTable[core.dpid].append({
                    'eth_dst' : h.eth,
                    'output' : [outport],
                    'priority' : 2,
                    'type' : 'dst'
                })

        # ASSIGNMENT 3:
        # Rules to Install:
        #   On the Edge Switches: output the appropriate port if the destination
        #   is a neighboring host (that is, don't send it up to a core switch).
        #   Otherwise, send to the core switch for that destination's vlan
        #   ("upward").  If a host has multiple VLANs, you can use the first
        #   in the list of VLANs.
        #   (Hint: you can look up the port of a neighboring host using
        #           topo.ports[edge switch name][host name]
        #   (Hint: to find a the VLAN, use topo.getVlanCore(vlanId))

        # [ADD YOUR CODE HERE]
        for edge in topo.edgeSwitches.values():
            routingTable[edge.dpid] = []
            for h in topo.hosts.values():
                # don't send edge switch's neighbors up to core
                if h.name in edge.neighbors:
                    outport = topo.ports[edge.name][h.name]
                else:
                    #pPfx = "BBI:StaticPolicy:build:" 
                    #print pPfx + "host h: " + h.name
                    #pprint(h)
                    thsVlanId = h.vlans[0]
                    #print pPfx + "host h.vlans[0]: %d" % (thsVlanId)
                    thsVlanCore = topo.getVlanCore(thsVlanId)
                    #print pPfx + "thsVlanId: VLANCore:" + thsVlanCore

                    #core = topo.coreSwitches.keys()[0]
                    #print pPfx + "core: "
                    #pprint(core)
                    outport = topo.ports[edge.name][thsVlanCore]

                routingTable[edge.dpid].append({
                    'eth_dst' : h.eth,
                    'output' : [outport],
                    'priority' : 2,
                    'type' : 'dst'
                })

        # [END MY CODE]

        return flood.add_arpflood(routingTable, topo)

class DefaultPolicy(object):
    def __init__(self, topo):
        self.routingTable = self.build(topo)

    def build(self, topo):
        routingTable = {}

        # use only one core switch
        core = topo.coreSwitches.keys()[0]
        coreDpid = topo.coreSwitches[core].dpid

        routingTable[coreDpid] = []

        # create rules for packets from core -> edge (downward)
        for h in topo.hosts.values():
            outport = topo.ports[core][h.switch]
            routingTable[coreDpid].append({
                'eth_dst' : h.eth,
                'output' : [outport],
                'priority' : 2,
                'type' : 'dst'
            })

        # create rules for packets from edge -> core (upward)
        for edge in topo.edgeSwitches.values():
            routingTable[edge.dpid] = []
            for h in topo.hosts.values():
                # don't send edge switch's neighbors up to core
                if h.name in edge.neighbors:
                    outport = topo.ports[edge.name][h.name]
                else:
                    outport = topo.ports[edge.name][core]

                routingTable[edge.dpid].append({
                    'eth_dst' : h.eth,
                    'output' : [outport],
                    'priority' : 2,
                    'type' : 'dst'
                })

        return flood.add_arpflood(routingTable, topo)

if __name__ == "__main__":
    class MockLogger(object):
        def info(self, msg, *args, **kwargs):
            pass

        def debug(self, msg, *args, **kwargs):
            pass

        def warning(self, msg, *args, **kwargs):
            pass

        def error(self, msg, *args, **kwargs):
            pass

        def critical(self, msg, *args, **kwargs):
            pass

        def log(self, msg, *args, **kwargs):
            pass

        def exception(self, msg, *args, **kwargs):
            pass

    class MockBandwidthStats(object):
        def __init__(self, topo):
            self.topo = topo
            self.hostBw = {}

        def addHostBwStat(self, host, txbytes, rxbytes):
            pass


    cfgfile = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "..", "config.txt"))
    if not os.path.isfile(cfgfile):
        print "Cannot run test without file", cfgfile
        print "To create file, run mdc (eg, sudo ./mdc --vid)"
        sys.exit(1)

    topo = Topology(cfgfile)
    policy = AdaptivePolicy(topo, MockBandwidthStats(topo), MockLogger())
    policy.utilization['s101'] = 100
    policy.utilization['s102'] = 50
    policy.utilization['s103'] = 200

    print "Testing with values:", str(policy.utilization)
    print "Expected min: s102"
    print "Your code returns min:", str(policy.minUtilization())
