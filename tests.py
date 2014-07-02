#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import ipaddress
import mock

import index


class TestFlaskStuff(unittest.TestCase):
    def test_localhost_is_in_127_block(self):
        self.assertTrue(index.is_ip_in_block('127.0.0.1', u'127.0.0.0/24'))

    def test_localhost_is_not_in_8_block(self):
        self.assertFalse(index.is_ip_in_block('127.0.0.1', u'8.0.0.0/24'))

    def test_get_event_should_return_the_expected_event(self):
        event = mock.Mock(spec=index.request)
        event.headers = {'X-GitHub-Event': 'push'}
        self.assertEquals(index.get_event(event), index.PUSH_EVENT)

if __name__ == '__main__':
    unittest.main()
