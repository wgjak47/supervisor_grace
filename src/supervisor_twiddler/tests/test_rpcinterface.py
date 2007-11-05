import sys
import unittest

import supervisor
from supervisor.xmlrpc import Faults as SupervisorFaults
from supervisor.supervisord import SupervisorStates

import supervisor_twiddler
from supervisor_twiddler.rpcinterface import Faults as TwiddlerFaults

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyPConfig, DummyProcess
from supervisor.tests.base import DummyPGroupConfig, DummyProcessGroup

class TestRPCInterface(unittest.TestCase):

    # Fault Constants

    def test_twiddler_fault_names_dont_clash_with_supervisord_fault_names(self):
        supervisor_faults = self.attrDictWithoutUnders(SupervisorFaults)
        twiddler_faults = self.attrDictWithoutUnders(TwiddlerFaults)

        for name in supervisor_faults.keys():
            self.assertNone(twiddler_faults.get(name))

    def test_twiddler_fault_codes_dont_clash_with_supervisord_fault_codes(self):
        supervisor_fault_codes = self.attrDictWithoutUnders(SupervisorFaults).values()
        twiddler_fault_codes = self.attrDictWithoutUnders(TwiddlerFaults).values()

        for code in supervisor_fault_codes:
            self.assertFalse(code in twiddler_fault_codes)

    # Constructor
    
    def test_ctor_assigns_supervisord(self):
        supervisord = DummySupervisor()
        interface = self.makeOne(supervisord)
    
        self.assertEqual(supervisord, interface.supervisord)

    # Factory
    
    def test_make_twiddler_rpcinterface_factory(self):
        from supervisor_twiddler import rpcinterface

        supervisord = DummySupervisor()
        interface = rpcinterface.make_twiddler_rpcinterface(supervisord)
        
        self.assertType(rpcinterface.TwiddlerNamespaceRPCInterface, interface)
        self.assertEquals(supervisord, interface.supervisord)

    # Updater
    
    def test_updater_raises_shutdown_error_if_supervisord_in_shutdown_state(self):
        supervisord = DummySupervisor(state = SupervisorStates.SHUTDOWN)
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.SHUTDOWN_STATE, 
                            interface.getAPIVersion)
    
    # API Method twiddler.getAPIVersion()
    
    def test_getAPIVersion_returns_api_version(self):
        supervisord = DummySupervisor()
        interface = self.makeOne(supervisord)
    
        version = interface.getAPIVersion()
        self.assertEqual('getAPIVersion', interface.update_text)
    
        from supervisor_twiddler.rpcinterface import API_VERSION
        self.assertEqual(version, API_VERSION)

    # API Method twiddler.getGroupNames()
    
    def test_getGroupNames_returns_empty_array_when_no_groups(self):
        supervisord = DummySupervisor()
        interface = self.makeOne(supervisord)
        
        names = interface.getGroupNames()
        self.assertType(list, names)
        self.assertEquals(0, len(names))
    
    def test_getGroupNames_returns_group_names(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)

        pgroups = {'foo': pgroup, 'bar': pgroup}
        supervisord = DummySupervisor(process_groups = pgroups)
        interface = self.makeOne(supervisord)
                
        names = interface.getGroupNames()
        self.assertType(list, names)
        self.assertEquals(2, len(names))
        names.index('foo')
        names.index('bar')
    
    # API Method twiddler.addGroup()
    
    def test_addGroup_raises_bad_name_when_group_name_already_exists(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)

        supervisord = DummySupervisor(process_groups = {'existing_group': pgroup})
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.BAD_NAME,
                            interface.addGroup,
                            'existing_group', 42)

    def test_addGroup_raises_incorrect_parameters_when_priority_not_int(self):
        supervisord = DummySupervisor()
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.INCORRECT_PARAMETERS,
                            interface.addGroup,
                            'new_group', 'not_an_int')

    def test_addGroup_adds_and_configures_new_group(self):
        supervisord = DummySupervisor()
        interface = self.makeOne(supervisord)
        self.assertTrue(interface.addGroup('new_group', 42))
        
        new_group = supervisord.process_groups.get('new_group')
        self.assertType(supervisor.process.ProcessGroup, new_group)

        config = new_group.config
        self.assertEquals('new_group', config.name)
        self.assertEquals(42, config.priority)
        self.assertEquals([], config.process_configs)
    
    # API Method twiddler.addProcessToGroup()
    
    def test_addProcessToGroup_raises_bad_name_when_group_doesnt_exist(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)

        supervisord = DummySupervisor(process_groups = {'foo': pgroup})
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.BAD_NAME,
                            interface.addProcessToGroup,
                            'nonexistant_group', 'foo', {})
    
    def test_addProcessToGroup_raises_bad_name_when_process_already_exists(self):
        pconfig = DummyPConfig(None, 'process_that_exists', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)

        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.BAD_NAME,
                            interface.addProcessToGroup,
                            'group_name', 'process_that_exists', {})
    
    def test_addProcessToGroup_raises_incorrect_params_when_poptions_is_not_dict(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
                
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
    
        bad_poptions = 42
        self.assertRPCError(SupervisorFaults.INCORRECT_PARAMETERS,
                            interface.addProcessToGroup,
                            'group_name', 'new_process', bad_poptions)
    
    def test_addProcessToGroup_raises_incorrect_params_when_poptions_is_invalid(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
                
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        supervisord.options = supervisor.options.ServerOptions()

        interface = self.makeOne(supervisord)

        poptions_missing_command = {}
        self.assertRPCError(SupervisorFaults.INCORRECT_PARAMETERS,
                            interface.addProcessToGroup,
                            'group_name', 'new_process', poptions_missing_command)        
    
    def test_addProcessToGroup_adds_new_process_to_supervisord_processes(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
        pgroup.processes = {}
        
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        supervisord.options = supervisor.options.ServerOptions()
        
        interface = self.makeOne(supervisord)
    
        poptions = {'command': '/usr/bin/find /'}
        self.assertTrue(interface.addProcessToGroup('group_name', 'new_process', poptions))
        self.assertEqual('addProcessToGroup', interface.update_text)
    
        process = pgroup.processes['new_process']

        self.assertType(supervisor.process.Subprocess, process)
        self.assertEqual('/usr/bin/find /', process.config.command)
    
    # API Method twiddler.removeProcessFromGroup()

    def test_removeProcessFromGroup_raises_bad_name_when_group_doesnt_exist(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)

        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.BAD_NAME,
                            interface.removeProcessFromGroup,
                            'nonexistant_group_name', 'process_name')
    
    def test_removeProcessFromGroup_raises_bad_name_when_process_does_not_exist(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
        pgroup.processes = {}
    
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(SupervisorFaults.BAD_NAME,
                            interface.removeProcessFromGroup,
                            'group_name', 'nonexistant_process_name')
    
    def test_removeProcessFromGroup_raises_still_running_when_process_has_pid(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        process = DummyProcess(pconfig)
        process.pid = 42

        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
        pgroup.processes = { 'process_with_pid': process }
    
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
        
        self.assertRPCError(TwiddlerFaults.STILL_RUNNING,
                            interface.removeProcessFromGroup,
                            'group_name', 'process_with_pid')
    
    def test_removeProcessFromGroup_transitions_process_group(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        process = DummyProcess(pconfig)

        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
        pgroup.processes = { 'process_name': process }
    
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
    
        result = interface.removeProcessFromGroup('group_name', 'process_name')
        self.assertTrue(result)
        self.assertTrue(pgroup.transitioned)
    
    def test_removeProcessFromGroup_deletes_the_process(self):
        pconfig = DummyPConfig(None, 'foo', '/bin/foo')
        process = DummyProcess(pconfig)

        gconfig = DummyPGroupConfig(None, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)   
        pgroup.processes = { 'process_name': process }
    
        supervisord = DummySupervisor(process_groups = {'group_name': pgroup})
        interface = self.makeOne(supervisord)
        
        result = interface.removeProcessFromGroup('group_name', 'process_name')
        self.assertTrue(result)
        self.assertNone(pgroup.processes.get('process_name'))
        self.assertEqual('removeProcessFromGroup', interface.update_text)

    # Helpers Methods
    
    def getTargetClass(self):
        from supervisor_twiddler.rpcinterface import TwiddlerNamespaceRPCInterface
        return TwiddlerNamespaceRPCInterface

    def makeOne(self, *arg, **kw):
        return self.getTargetClass()(*arg, **kw)

    def attrDictWithoutUnders(self, obj):
        """ Returns the __dict__ for an object with __unders__ removed """
        attrs = {}
        for k, v in obj.__dict__.items():
            if not k.startswith('__'): attrs[k] = v
        return attrs

    # Helper Assertion Methods

    def assertRPCError(self, code, callable, *args, **kw):
        try:
            callable(*args, **kw)
        except supervisor.xmlrpc.RPCError, inst:
            self.assertEqual(inst.code, code)
        else:
            self.fail('RPCError was never raised')

    def assertTrue(self, obj):
        self.assert_(obj is True)

    def assertFalse(self, obj):
        self.assert_(obj is False)
    
    def assertNone(self, obj):
        self.assert_(obj is None)

    def assertType(self, typeof, obj):
        self.assertEqual(True, isinstance(obj, typeof), 'type mismatch')


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')