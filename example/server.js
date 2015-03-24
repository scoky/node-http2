#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var url = require('url')

// Parse argv
var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 2) {
  console.log('USAGE: node server.js <bind> <cache directory> [-p] [-k] [-v] [-h]')
  console.log('-p use plaintext with client')
  console.log('-v verbose output')
  console.log('-k ignore certificate errors')
  console.log('-h print this help menu')
  process.exit()
}

if (argv.k) {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"
}

var options = argv.p ? {
  plain: true
} : {
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
};
// Passing bunyan logger (optional)
options.log = require('../test/util').createLogger('server')

var bind = argv._[0]
var directory = argv._[1]

var request_count = 0

function onRequest(request, response) {
  var req_no = request_count++
  if (argv.v) {
    console.log((new Date()).toISOString()+" Request #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))
  }

  var hostname = request.headers[':authority'] || request.headers['host']
  var dir = path.join(directory, hostname)
  var details = url.parse(request.url)
  if (path.extname(details.pathname)) {
    details.filename = path.basename(details.pathname)
    details.directory = path.dirname(details.pathname)
  } else {
    details.filename = 'index.html'
    details.directory = details.pathname
  }
  var filename = path.join(path.join(dir, details.directory), details.filename)

  var rf = fs.createReadStream(filename)
  rf.on('error', function() {
    console.log((new Date()).toISOString()+" Could not find: "+request.url)
    response.writeHead(404)
    response.end()
  })
  rf.pipe(response)

 /* fs.readFile(filename, 'utf8', function(err, data) {
    if (err) {
      console.log((new Date()).toISOString()+" Resource list: "+dir+" Error:"+err)
      send404()
      return
    }
    data = JSON.parse(data)
    for (key in data) {
      if (url.parse(key).path === url_path && (data[key].responseCode >= 100 && data[key].responseCode < 600)) {
        console.log((new Date()).toISOString()+" Response #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))
        response.writeHead(data[key].responseCode, http2.convertHeadersToH2(data[key].headers))
	var rf = fs.createReadStream(path.join(dir, data[key].ref+'.response'))//.pipe(response)
	rf.on('data', function(chunk) {
	  response.write(chunk)
	})
	rf.on('end', function() {
	  response.end()
	})
        return
      }
    }
    send404()
  })
  function send404() {
    console.log((new Date()).toISOString()+" Could not find: "+request.url)
    response.writeHead(404)
    response.end()
  }*/
}

// Creating the server
if (argv.p) {
  server = http2.raw.createServer(options, onRequest);
} else {
  server = http2.createServer(options, onRequest);
}

ip = bind.split(':')[0]
port = bind.split(':')[1]
server.listen(port, ip)
