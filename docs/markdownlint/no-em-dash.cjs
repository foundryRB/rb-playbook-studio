"use strict";

module.exports = {
  names: ["no-em-dash"],
  description: "Use commas, periods, colons, or regular dashes instead of em dashes",
  tags: ["style"],
  parser: "micromark",
  function: function noEmDash(params, onError) {
    if (params.frontMatterLines.some((line) => line.includes("\u2014"))) {
      onError({ lineNumber: 1, detail: "Em dash in frontmatter" });
    }
    params.lines.forEach((line, index) => {
      const column = line.indexOf("\u2014");
      if (column !== -1) {
        onError({ lineNumber: index + 1, range: [column + 1, 1] });
      }
    });
  }
};
