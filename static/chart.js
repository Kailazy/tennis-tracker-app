function chart() {
	var width = 640, // default width
		height = 150; // default height

	// Read URL parameters
	var vars = {}, hash;
	var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
	for (var i = 0; i < hashes.length; i++) {
		hash = hashes[i].split('=');
		vars[hash[0]] = hash[1] == 0 ? 0 :
						hash[1] == "false" ? false :
						hash[1];
	}

	function my() {
		// generate chart here, using `width` and `height`
		var svg = d3.select("svg"),
		margin = {top: 20, right: 20, bottom: 30, left: 50},
		width = +svg.attr("width") - margin.left - margin.right,
		height = +svg.attr("height") - margin.top - margin.bottom;

		svg.append("g")
			.attr("class", "viewport")
			.attr("transform", "translate(" + margin.left + "," + margin.top + ")");

		var x = d3.scaleTime()
			.rangeRound([0, width]);
		
		var y = d3.scaleLinear()
			.rangeRound([height, 0]);
		
		var line = d3.line()
			.x(function(d) { return x(d.timestamp); })
			.y(function(d) { return y(d.voltage); });

		var renderData = function(error, data) {
			if (error) throw error;

			g = svg.select(".viewport");
			
			x.domain(d3.extent(data, function(d) { return d.timestamp; }));
			y.domain(d3.extent(data, function(d) { return d.voltage; }));
			
			g.select(".axis--x").remove();
			g.append("g")
				.attr("class", "axis axis--x")
				.attr("transform", "translate(0," + height + ")")
				.call(d3.axisBottom(x)
						.tickFormat(d3.timeFormat("%H:%M:%S.%L")));
			
			g.select(".axis--y").remove();
			g.append("g")
				.attr("class", "axis axis--y")
				.call(d3.axisLeft(y))
				.append("text")
				.attr("fill", "#000")
				.attr("transform", "rotate(-90)")
				.attr("y", 6)
				.attr("dy", "0.71em")
				.style("text-anchor", "end")
				.text("Voltage");
			
			g.select(".line").remove();
			g.append("path")
				.datum(data)
				.attr("class", "line")
				.attr("d", line);

			g.select(".focus").remove();
			var focus = g.append("g")
				.attr("class", "focus")
				.style("display", "none");

			focus.append("circle")
				.attr("class", "circle")
				.attr("r", 5);

			focus.append("rect")
				.attr("class", "tooltip")
				.attr("width", 200)
				.attr("height", 50)
				.attr("x", 10)
				.attr("y", -22)
				.attr("rx", 4)
				.attr("ry", 4);

			focus.append("text")
				.attr("class", "tooltip-timestamp")
				.attr("x", 18)
				.attr("y", -2);

			focus.append("text")
				.attr("x", 18)
				.attr("y", 18)
				.text("Voltage:");

			focus.append("text")
				.attr("class", "tooltip-value")
				.attr("x", 70)
				.attr("y", 18);

			g.select(".overlay").remove();
			g.append("rect")
				.attr("class", "overlay")
				.attr("width", width)
				.attr("height", height)
				.on("mouseover", function() { focus.style("display", null); })
				.on("mouseout", function() { focus.style("display", "none"); })
				.on("mousemove", mousemove);

			function mousemove() {
				var x0 = x.invert(d3.mouse(this)[0]),
					ii = 0;
					d = data.find(function(e,i) { ii = i; return e.timestamp > x0; } );
					d = data[ii>0 ? ii-1 : ii];
				if (d) {
					focus.attr("transform", "translate(" + (x(d.timestamp) + 200 > width ? x(d.timestamp) - 210 : x(d.timestamp)) + "," + y(d.voltage) + ")");
					focus.select(".tooltip").attr("x", x(d.timestamp) + 200 > width ? 0 : 10);
					focus.select(".circle").attr("cx", x(d.timestamp) + 200 > width ? 210 : 0);
					focus.select(".tooltip-timestamp").text(d.time);
					focus.select(".tooltip-value").text(d.voltage + " V");
				}
			}
		}
  	}
  
	my.width = function(value) {
	  if (!arguments.length) return width;
	  width = value;
	  return my;
	};
  
	my.height = function(value) {
	  if (!arguments.length) return height;
	  height = value;
	  return my;
	};

	var max_time = "";
	var data = [];

	function refresh() {
		d3.json(vars['src'] ? vars['src'] : `/events?type=voltage_stats&limit=99999&since=${max_time}`).then(function(results) {
			results = results.filter(function(d) {
				if (!d.voltage) return false;
				if (d.voltage < 5) return false;
				d.timestamp = parseDate(d.time.match(/.+[.]\d\d\d/));	// cut milliseconds only to 3 digits
				max_time = max_time < d.time ? d.time : max_time;
				return true;
			})

			results.sort(function(a, b) {
				return a.timestamp - b.timestamp;
			});

			data = data.concat(results);

			renderData(false, data);
		});

		setTimeout(refresh, 60000);
	}

	refresh();

	return my;
}
