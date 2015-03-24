#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var crypto = require('crypto');
var url = require('url')

// Parse argv
var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node h2-proxy-h2.js <bind> [-p] [-l] [-k] [-v] [-h] [-a upstream hostname] [-r upstream port]')
  console.log('-p use plaintext with client')
  console.log('-l use plaintext with server')
  console.log('-v verbose output')
  console.log('-k ignore certificate errors')
  console.log('-a upstream hostname (default to client header)')
  console.log('-r upstream port number (default to 80 or 443 depending on -p)')
  console.log('-h print this help menu')
  process.exit()
}

var options = argv.p ? {
  plain: true
} : {
  // Dud certificate to issue to clients
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
}

// Passing bunyan logger to http2 server
options.log = require('../test/util').createLogger('server')
// Passing bunyan logger to http2
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})

if (argv.k) {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"
}

var request_count = 0

var sh2 = (argv.l ? http2.raw : http2)
var ch2 = (argv.p ? http2.raw : http2)
// Creating HTTP2 server to listen for incoming requests from client
var server = ch2.createServer(options, function(request, response) {
  var req_no = request_count++
  if (argv.v) {
    console.log((new Date()).toISOString()+" h2-to-h2 request: #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))
  }

  var poptions = url.parse(request.url)
  poptions.headers = http2.convertHeadersToH2(request.headers)
  poptions.servername = poptions.host = poptions.hostname = (argv.a ? argv.a : poptions.headers[':authority'])
  poptions.protocol = (argv.l ? 'http:' : 'https:')
  poptions.port = (argv.r ? argv.r : (argv.l ? 80 : 443))
  poptions.slashes = true
  poptions.href = poptions.url = url.format(poptions)
  poptions.plain = argv.l
 
  // Send the request to the content server
  if (argv.v) {
    console.log((new Date()).toISOString()+" h2-to-h2 request: #"+req_no+"# "+JSON.stringify(poptions))
  }

  var prequest = sh2.request(poptions)
  // Receiving the response from content server
  prequest.on('response', function(presponse) {
    if (argv.v) {
      console.log((new Date()).toISOString()+" h2-to-h2 response: #"+req_no+"# "+presponse.statusCode+" "+JSON.stringify(presponse.headers))
    }
    var rheaders = http2.convertHeadersToH2(presponse.headers)
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
      // Send back an error
      response.writeHead(502)
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

// Listen on port
ip = argv._[0].split(':')[0]
port = argv._[0].split(':')[1]
server.listen(port, ip)
