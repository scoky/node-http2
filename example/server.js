#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var url = require('url')

var options = process.env.HTTP2_PLAIN ? {
  plain: true
} : {
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
};

// Passing bunyan logger (optional)
options.log = require('../test/util').createLogger('server')

var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node server.js <cache directory> [-h]')
  console.log('-h print this help menu')
  process.exit()
}
var directory = argv._[0]

var request_count = 0

// Creating the server
var server = http2.createServer(options, function(request, response) {
  var req_no = request_count++
  console.log((new Date()).toISOString()+" Request #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))

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
})

server.listen(process.env.HTTP2_PORT || 5678);
