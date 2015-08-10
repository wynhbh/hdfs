#!/usr/bin/env python
# encoding: utf-8

"""Test Hdfs client interactions with HDFS."""

from hdfs.client import Client
from hdfs.util import *
from nose.tools import eq_, raises
from string import Template
import os


class TestConfig(object):

  def test_rcpath(self):
    rcpath = os.getenv('HDFSCLI_CONFIG')
    try:
      with temppath() as tpath:
        os.environ['HDFSCLI_CONFIG'] = tpath
        with open(tpath, 'w') as writer:
          writer.write('[foo]\nbar=hello')
        eq_(Config().get('foo', 'bar'), 'hello')
    finally:
      if rcpath:
        os['HDFSCLI_CONFIG'] = rcpath
      else:
        os.unsetenv('HDFSCLI_CONFIG')

  def test_parse_boolean(self):
    eq_(Config.parse_boolean(True), True)
    eq_(Config.parse_boolean(False), False)
    eq_(Config.parse_boolean(''), False)
    eq_(Config.parse_boolean('False'), False)
    eq_(Config.parse_boolean('true'), True)
    eq_(Config.parse_boolean('yes'), True)
    eq_(Config.parse_boolean(None), False)

  def _write_client_module(self, path, class_name):
    template = osp.join(osp.dirname(__file__), 'dat', 'client_template.py')
    with open(template) as reader:
      contents = Template(reader.read()).substitute({
        'class_name': class_name,
      })
    with open(path, 'w') as writer:
      writer.write(contents)

  def test_autoload_client_from_path(self):
    with temppath() as module_path:
      self._write_client_module(module_path, 'PathClient')
      with temppath() as config_path:
        config = Config(config_path)
        config.add_section(config.global_section)
        config.set(config.global_section, 'autoload.paths', module_path)
        config._autoload()
        client = Client._from_options('PathClient', {'url': ''})
        eq_(client.one, 1)

  def test_autoload_client_from_module(self):
    with temppath() as module_dpath:
      os.mkdir(module_dpath)
      sys.path.append(module_dpath)
      module_fpath = osp.join(module_dpath, 'mclient.py')
      self._write_client_module(module_fpath, 'ModuleClient')
      try:
        with temppath() as config_path:
          config = Config(config_path)
          config.add_section(config.global_section)
          config.set(config.global_section, 'autoload.modules', 'mclient')
          config._autoload()
          client = Client._from_options('ModuleClient', {'url': ''})
          eq_(client.one, 1)
      finally:
        sys.path.remove(module_dpath)


class TestHuman(object):

  def test_hsize(self):
    eq_(hsize(0), '   0 B')
    eq_(hsize(1023), '1023 B')
    eq_(hsize(1024), '   1kB')

  def test_htime(self):
    eq_(htime(0), ' 0.0s')
    eq_(htime(50), '50.0s')
    eq_(htime(60), ' 1.0m')
    eq_(htime(90), ' 1.5m')
    eq_(htime(3600), ' 1.0h')
    eq_(htime(3600 * 24 * 7 * 4 * 12 * 24), '24.0Y')


class TestAsyncWriter(object):

  def test_basic(self):
    result = []
    def consumer(gen):
      result.append(list(gen))
    with AsyncWriter(consumer) as writer:
      writer.write(1)
      writer.write(2)
    eq_(result, [[1,2]])

  def test_multiple_writer_uses(self):
    result = []
    def consumer(gen):
      result.append(list(gen))
    writer = AsyncWriter(consumer)
    with writer:
      writer.write(1)
      writer.write(2)
    with writer:
      writer.write(3)
      writer.write(4)
    eq_(result, [[1,2],[3,4]])

  def test_multiple_consumer_uses(self):
    result = []
    def consumer(gen):
      result.append(list(gen))
    with AsyncWriter(consumer) as writer:
      writer.write(1)
      writer.write(2)
    with AsyncWriter(consumer) as writer:
      writer.write(3)
      writer.write(4)
    eq_(result, [[1,2],[3,4]])

  @raises(ValueError)
  def test_nested(self):
    result = []
    def consumer(gen):
      result.append(list(gen))
    with AsyncWriter(consumer) as _writer:
      _writer.write(1)
      with _writer as writer:
        writer.write(2)

  @raises(HdfsError)
  def test_child_error(self):
    def consumer(gen):
      for value in gen:
        if value == 2:
          raise HdfsError('Yo')
    with AsyncWriter(consumer) as writer:
      writer.write(1)
      writer.write(2)

  @raises(HdfsError)
  def test_parent_error(self):
    def consumer(gen):
      for value in gen:
        pass
    def invalid(w):
      w.write(1)
      raise HdfsError('Ya')
    with AsyncWriter(consumer) as writer:
      invalid(writer)
