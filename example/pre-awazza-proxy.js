#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var http = require("http")
var https = require('https')
var crypto = require('crypto');
var url = require('url')

var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node pre-awazza-proxy.js <bind> [-p] [-l] [-k] [-v] [-h] [-c] [-a upstream hostname] [-r upstream port]')
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

var options = argv.p ? {
  plain: true
} : {
  // Dub certificate to issue to clients
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
}

// Passing bunyan logger to http2 server
options.log = require('../test/util').createLogger('server')

if (argv.k) {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"
}

// To get servername from TLS handshake
// Could use to parallelize post- TLS handshake
// Unfortunately, the 'servername' is the proxy, not the content server
/*options.SNICallback = function (servername) {
  console.log('Incoming TLS session for '+servername)
  var details = {
    key: options.key,
    cert: options.cert
  }
  return crypto.createCredentials(details).context
}*/

var request_count = 0

var h1 = (argv.l ? http : https)
var h2 = (argv.p ? http2.raw : http2)
// Creating HTTP2 server to listen for incoming requests from client
var server = h2.createServer(options, function(request, response) {
  var req_no = request_count++
  if (argv.v) {
    console.log((new Date()).toISOString()+" Pre received request: #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))
  }

  var poptions = url.parse(request.url)
  // Convert the http/2 headers received from the client into http/1.1 headers for Awazza
  poptions.headers = http2.convertHeadersFromH2(request.headers)
  poptions.host = poptions.hostname = poptions.headers.host
  poptions.href = poptions.url = url.format(poptions)
  // Replace the upstream hostname
  poptions.host = poptions.hostname = (argv.a ? argv.a : poptions.hostname)
  poptions.port = (argv.r ? argv.r : (argv.l ? 80 : 443))
  poptions.protocol = (argv.l ? 'http:' : 'https:')
  poptions.plain = argv.l

  // Do not attempt to pool connections. This tells node to immediately send the request upstream
  if (!argv.c) {
    poptions.agent = false
  }
  // Header to indicate which proxy sent this request
  poptions.headers['proxy-type'] = 'nodejs'
 
  // Send http/1.1 request to Awazza
  var prequest = h1.request(poptions, function (presponse) {
    if (argv.v) {
      console.log((new Date()).toISOString()+" Pre received response: #"+req_no+"# "+presponse.statusCode+" "+JSON.stringify(presponse.headers))
    }
    var rheaders = http2.convertHeadersToH2(presponse.headers)
    // Response contains a location. Convert the location to plain or cipher for the client
    if (rheaders.location) {
      var location = url.parse(url.resolve(poptions.url, rheaders.location))
      location.protocol = (argv.p ? 'http:' : 'https:')
      rheaders.location = url.format(location)
    }
    
    // Convert and write the headers
    response.writeHead(presponse.statusCode, '', rheaders)
    // Pipe the response from Awazza to the client
    presponse.pipe(response)

    presponse.on('error', function (err) {
      // Return an error to the client
      console.log((new Date()).toISOString()+' PResponse Error: '+err)
      response.writeHeader(502)
      response.end()
    })
  })

  // Send post data
  if (poptions.headers['content-length'] > 0) {
    request.pipe(prequest)
  } else {
    prequest.end()
  }

  // ERROR HANDLING
  request.on('error', function (err) {
    // Error on request from client
    // Nothing to be done except log the event
    console.log((new Date()).toISOString()+' Request Error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log((new Date()).toISOString()+' Response Error: '+err)
  })
  prequest.on('error', function (err) {
    // Return an error to the client
    console.log((new Date()).toISOString()+' PRequest Error: '+err)
    response.writeHead(502)
    response.end()
  })
})

ip = argv._[0].split(':')[0]
port = argv._[0].split(':')[1]
server.listen(port, ip)
