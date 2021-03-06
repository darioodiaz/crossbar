###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

from autobahn.wamp.exception import ApplicationError

from twisted.python import log



class ComponentSessionFactory:

   session = None

   def __init__(self, realm):
      self._realm = realm

   def __call__(self):
      session = self.session(self._realm)
      session.factory = self
      return session



class ComponentModule:
   """
   """

   def __init__(self, session, pid):
      self._session = session
      self._pid = pid
      self._client = None

      self.debug = self._session.factory.options.debug

      session.register(self.start, 'crossbar.node.module.{}.component.start'.format(self._pid))


   def start(self, transport, klassname, realm):
      """
      Dynamically start an application component to run next to the router in "embedded mode".
      """

      ## dynamically load the application component ..
      ##
      try:
         if self.debug:
            log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self._pid, klassname, realm))

         import importlib
         c = klassname.split('.')
         mod, klass = '.'.join(c[:-1]), c[-1]
         app = importlib.import_module(mod)
         SessionKlass = getattr(app, klass)

      except Exception as e:
         if self.debug:
            log.msg("Worker {}: failed to import class - {}".format(e))
         raise ApplicationError("crossbar.error.class_import_failed", str(e))

      else:
         ## create a WAMP application session factory
         ##
         #from autobahn.twisted.wamp import ApplicationSessionFactory
         #session_factory = ApplicationSessionFactory()
         session_factory = ComponentSessionFactory(realm)
         session_factory.session = SessionKlass

         ## create a WAMP-over-WebSocket transport client factory
         ##
         from autobahn.twisted.websocket import WampWebSocketClientFactory
         transport_factory = WampWebSocketClientFactory(session_factory, transport['url'], debug = self.debug)
         transport_factory.setProtocolOptions(failByDrop = False)

         ## start a WebSocket client from an endpoint
         ##
         from twisted.internet import reactor
         from twisted.internet.endpoints import TCP4ClientEndpoint, SSL4ClientEndpoint, UNIXClientEndpoint
         from twisted.internet.endpoints import clientFromString
         from tlsctx import TlsClientContextFactory


         if False:
            self._client = clientFromString(reactor, transport['endpoint'])
         else:
            try:
               endpoint_config = transport.get('endpoint')

               ## a TCP4 endpoint
               ##
               if endpoint_config['type'] == 'tcp':

                  ## the host to connect ot
                  ##
                  host = str(endpoint_config['host'])

                  ## the port to connect to
                  ##
                  port = int(endpoint_config['port'])

                  ## connection timeout in seconds
                  ##
                  timeout = int(endpoint_config.get('timeout', 10))

                  if 'tls' in endpoint_config:

                     ctx = TlsClientContextFactory()

                     ## create a TLS client endpoint
                     ##
                     self._client = SSL4ClientEndpoint(reactor,
                                                       host,
                                                       port,
                                                       ctx,
                                                       timeout = timeout)
                  else:
                     ## create a non-TLS client endpoint
                     ##
                     self._client = TCP4ClientEndpoint(reactor,
                                                       host,
                                                       port,
                                                       timeout = timeout)

               ## a Unix Domain Socket endpoint
               ##
               elif endpoint_config['type'] == 'unix':

                  ## the path
                  ##
                  path = str(endpoint_config['path'])

                  ## connection timeout in seconds
                  ##
                  timeout = int(endpoint_config['type'].get('timeout', 10))

                  ## create the endpoint
                  ##
                  self._client = UNIXClientEndpoint(reactor, path, timeout = timeout)

               else:
                  raise ApplicationError("crossbar.error.invalid_configuration", "invalid endpoint type '{}'".format(endpoint_config['type']))

            except Exception as e:
               log.msg("endpoint creation failed: {}".format(e))
               raise e


         retry = True
         retryDelay = 1000

         def try_connect():
            print "Trying to connect .."
            d = self._client.connect(transport_factory)

            def success(res):
               if True or self.debug:
                  log.msg("Worker {}: client connected to router".format(self._pid))

            def error(err):
               log.msg("Worker {}: client failed to connect to router - {}".format(self._pid, err))
               if retry:
                  log.msg("Worker {}: retrying in {} ms".format(self._pid, retryDelay))
                  reactor.callLater(float(retryDelay) / 1000., try_connect)
               else:
                  log.msg("Worker {}: giving up.".format(seld._pid))

            d.addCallbacks(success, error)

         try_connect()
