var fs = require('fs');
var path = require('path');
var http2 = require('..');

var options = process.env.HTTP2_PLAIN ? {
  plain: true
} : {
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
};

// Passing bunyan logger (optional)
options.log = require('../test/util').createLogger('server');
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
});

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

// Creating the server
var server = http2.createServer(options, function(request, response) {
  var poptions = require('url').parse(request.url);
  poptions.protocol = process.env.UP_PROTOCOL+':'; // Awazza always uses http
  poptions.hostname = process.env.UP_SERVER; // Location of upstream server, either awazza testing proxy or webserver
  poptions.port = process.env.UP_PORT;
  var prequest = http2.request(poptions);
  prequest.end();

  // Receiving the response
  prequest.on('response', function(presponse) {  
    presponse.pipe(response);
  });
});

server.listen(process.env.HTTP2_PORT || 8080);
