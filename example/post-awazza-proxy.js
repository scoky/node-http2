#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var http = require('http')
var https = require('https')
var url = require('url')

var TIMEOUT = 5000 // Give up on requests after 5 secs

var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node post-awazza-proxy.js <bind> [-p] [-l] [-k] [-v] [-h] [-c] [-a upstream hostname] [-r upstream port]')
  console.log('-p use plaintext with client')
  console.log('-l use plaintext with server')
  console.log('-v verbose output')
  console.log('-k ignore certificate errors')
  console.log('-c use h1 connection pooling')
  console.log('-a upstream hostname (default to client header)')
  console.log('-r upstream port number (default to 80 or 443 depending on -p)')
  console.log('-h print this help menu')
  process.exit()
}

// Passing bunyan logger to http2
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})

if (argv.k) {
  // Do not validate server certificate
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"
}
var request_count = 0

var h1 = (argv.p ? http : https)
var h2 = (argv.l ? http2.raw : http2)
// Creating an HTTP1.1 server to listen for incoming requests from Awazza
var server = h1.createServer(function(request, response) {
  var req_no = request_count++
  if (argv.v) {
    console.log((new Date()).toISOString()+" Post received request: #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))
  }

  // Determine upstream server from requested URL
  var poptions = url.parse(request.url)

  // Always send request via HTTP2 over TLS
  poptions.protocol = (argv.l ? 'http:' : 'https:')
  poptions.port = (argv.r ? argv.r : (argv.l ? 80 : 443))
  // Convert the http/1.1 headers from the client into http/2 headers
  poptions.headers = http2.convertHeadersToH2(request.headers)
  // Update the href to reflect the content server
  poptions.servername = poptions.host = poptions.hostname = poptions.headers[':authority']
  poptions.href = poptions.url = url.format(poptions)
  poptions.host = poptions.hostname = (argv.a ? argv.a : poptions.hostname)
  poptions.plain = argv.l

  // Send the request to the content server
  //console.log("Sending request: "+JSON.stringify(poptions))
  var prequest = h2.request(poptions)
  // Receiving the response from content server
  prequest.on('response', function(presponse) {  
    if (argv.v) {
      console.log((new Date()).toISOString()+" Post received response: #"+req_no+"# "+presponse.statusCode+" "+JSON.stringify(presponse.headers))
    }
    var rheaders = http2.convertHeadersFromH2(presponse.headers)
    // Response contains a location. Convert the location to plain or cipher for the client
    if (rheaders.location) {
      var location = url.parse(url.resolve(poptions.url, rheaders.location))
      location.protocol = (argv.p ? 'http:' : 'https:')
      rheaders.location = url.format(location)
    }

    response.writeHead(presponse.statusCode, '', rheaders)
    // Pipe response to client
    presponse.pipe(response)

    presponse.on('error', function(err) {
      console.log((new Date()).toISOString()+' PResponse Error: '+err)
      // Something went wrong, send client a 502 error
      response.writeHead(502)
      response.end()
    })
  })

  if (poptions.headers['content-length'] > 0) {
    request.pipe(prequest)
  } else {
    prequest.end()
  }

  // ERROR HANDLING
  request.on('error', function (err) {
    // Error on request from client
    // Nothing to be done except log the event
    console.log((new Date()).toISOString()+' Request error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log((new Date()).toISOString()+' Response error: '+err)
  })
  prequest.on('error', function (err) {
    console.log((new Date()).toISOString()+' PRequest error: '+err)
    // Something went wrong during request to content server
    // Send Awazza a 502 error
    response.writeHead(502)
    response.end()
  })
  // Timeout only applied to HTTP session, not TCP connect
  /*prequest.setTimeout(5000, function () {
    console.log('PRequest timed out')
    // Request timedout to content server
    prequest.abort()
    // Tell Awazza about the timeout
    response.writeHead(504)
    response.end()
  })*/
})

/*server.on('error', function(err) { // This will never catch an error?
  console.log('Server error: '+err)
})*/

ip = argv._[0].split(':')[0]
port = argv._[0].split(':')[1]
server.listen(port, ip)

