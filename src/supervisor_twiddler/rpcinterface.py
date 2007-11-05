import os

from supervisor.options import UnhosedConfigParser
from supervisor.options import ProcessGroupConfig
from supervisor.supervisord import SupervisorStates
from supervisor.xmlrpc import Faults as SupervisorFaults
from supervisor.xmlrpc import RPCError
from supervisor.http import NOT_DONE_YET

API_VERSION = '0.1'

class Faults:
    STILL_RUNNING = 220

class TwiddlerNamespaceRPCInterface:
    """ A supervisor rpc interface that facilitates manipulation of 
    supervisor's configuration and state in ways that are not 
    normally accessible at runtime.
    """
    def __init__(self, supervisord):
        self.supervisord = supervisord

    def _update(self, text):
        self.update_text = text # for unit tests, mainly

        state = self.supervisord.get_state()

        if state == SupervisorStates.SHUTDOWN:
            raise RPCError(SupervisorFaults.SHUTDOWN_STATE)

        # XXX fatal state
        
    # RPC API methods

    def getAPIVersion(self):
        """ Return the version of the RPC API used by supervisor_twiddler

        @return int version version id
        """
        self._update('getAPIVersion')
        return API_VERSION

    def getGroupNames(self):
        """ Return an array with the names of the process groups.
        
        @return array                Process group names
        """
        self._update('getGroupNames')
        return self.supervisord.process_groups.keys()

    def addGroup(self, name, priority):
        """ Add a new, empty process group.
        
        @param string   name         Name for the new process group
        @param integer  priority     Group priority (same as supervisord.conf)
        @return boolean              Always True unless error
        """
        self._update('addGroup')
        
        # check group_name does not already exist
        if self.supervisord.process_groups.get(name) is not None:
            raise RPCError(SupervisorFaults.BAD_NAME, name)

        # check priority is sane
        try:
            int(priority)
        except ValueError, why:
            raise RPCError(SupervisorFaults.INCORRECT_PARAMETERS, why[0])            

        # make a new group with no process configs
        options = self.supervisord.options
        config = ProcessGroupConfig(options, name, priority, [])
        group = config.make_group()

        # add new process group
        self.supervisord.process_groups[name] = group
        return True

    def addProcessToGroup(self, group_name, process_name, poptions):
        """ Add a process to a process group.

        @param string  group_name    Name of an existing process group
        @param string  process_name  Name of the new process in the process table
        @param struct  poptions      Program options, same as in supervisord.conf
        @return boolean              Always True unless error
        """
        self._update('addProcessToGroup')

        group = self._getProcessGroup(group_name)

        # check process_name does not already exist in the group
        for config in group.config.process_configs:
            if config.name == process_name:
                raise RPCError(SupervisorFaults.BAD_NAME)

        # make configparser instance for program options
        section_name = 'program:%s' % process_name
        parser = self._makeConfigParser(section_name, poptions)

        # make programs list from parser instance 
        options = self.supervisord.options
        try:
            programs = options.processes_from_section(parser, section_name, group_name)
        except ValueError, why:
            raise RPCError(SupervisorFaults.INCORRECT_PARAMETERS, why[0])

        # make process and add
        config = programs[0]
        config.create_autochildlogs() # XXX hack
        group.processes[process_name] = config.make_process(group)
        return True

    def removeProcessFromGroup(self, group_name, process_name):
        """ Remove a process from a process group.

        @param string group_name    Name of an existing process group
        @param string process_name  Name of the process to remove from group
        @return boolean             Always return True unless error
        """
        self._update('removeProcessFromGroup')

        group = self._getProcessGroup(group_name)

        # check process exists and is running
        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(SupervisorFaults.BAD_NAME, process_name)
        if process.pid:
            raise RPCError(Faults.STILL_RUNNING, process_name)

        group.transition()

        del group.processes[process_name]
        return True

    def _getProcessGroup(self, name):
        """ Find a process group by its name """
        group = self.supervisord.process_groups.get(name)
        if group is None:
            raise RPCError(SupervisorFaults.BAD_NAME, 'group: %s' % name)
        return group

    def _makeConfigParser(self, section_name, options):
        """ Populate a new UnhosedConfigParser instance with a 
        section built from an options dict.
        """
        config = UnhosedConfigParser()
        try:
            config.add_section(section_name)
            for k, v in dict(options).items():
                config.set(section_name, k, v)
        except (TypeError, ValueError):
            raise RPCError(SupervisorFaults.INCORRECT_PARAMETERS)        
        return config

def make_twiddler_rpcinterface(supervisord, **config):
    return TwiddlerNamespaceRPCInterface(supervisord)