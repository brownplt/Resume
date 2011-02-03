
function highlightBatchCheckboxes() {
  var elts = getElementsByClass('batchCheckbox');
  for (var ix = 0; ix < elts.length; ix++)
    { elts[ix].style.border = "2px solid red"; }
};
 
function AppTableWidget() {
	TableWidget.apply(this,arguments);
}
inheritFrom(AppTableWidget,TableWidget);
AppTableWidget.prototype.makePaginator = function(numPapersB,cl) {
	var isp = pagesizecookie.parseJSON();
	var pw = new PaginatorWidget(numPapersB,cl,isp[0],isp[1]);
	lift_b(function(ps,pn) {
		setCookie('appage',10,[ps,pn].toJSONString());
	},pw.behaviors.size,pw.behaviors.page);
	return pw;
}
AppTableWidget.prototype.makeSorter = function(columns) {
	var initsort = undefined;
	if(sortcookie) initsort = sortcookie.parseJSON();
	var hsw = new HeaderSortWidget(columns,initsort);
	hsw.behaviors.cols.transform_b(function(sc) {
		setCookie('appsort',10,sc.toJSONString());
	});
	return hsw;
};

function ApplicantEntry(rinfo,basicInfo,app,cols,nsorder) {
	var me = this;
	this.info = app;
	this.id = this.info.id;
	this.statements = {};
	map(function(s) {me.statements[s] = true;},this.info.statements);

	this.rstatus = 'none';
	map(function(r) {if (r.rname == rinfo.auth.username) me.rstatus = 'reviewed';},this.info.reviews);
	map(function(r) {if (r.rname == rinfo.auth.username) me.rstatus = 'comment';},this.info.comments);

	this.highlighted = inList(this.id,rinfo.highlights);
	this.hidden = inList(this.id,rinfo.hiddens);

	this.nsorder = nsorder;

	this.areasort = fold(function(v, acc) {return acc + v;},'',map(function(k) {return k.name;},this.info.areas).sort());

	this.makeSecondRow = function() {
	    return TR({className:'secondrow'},
		    TD({colSpan:1},' '),
		    TD({colSpan:5+basicInfo.statements.length},
			this.rejectDom,
			P(STRONG('References: '),
			    this.info.refletters.length == 0 ? 'None Yet' :
			    fold(function(rl,acc) {
				return (acc.length ? acc.concat([', ']) : acc).concat(
				    rl.submitted ? 
				    [A({href:'letter-'+rl.id+'.pdf?cookie='+authCookie},rl.name)] : 
				    [rl.name]);
				},[],this.info.refletters)),
			P(STRONG('Reviews: '),
			    this.info.reviews.length == 0 ? 'None Yet' :
			    map(function(rev) {
				svstr = '';
				if(rev.svals.length)
				    svstr = ' (' +
					    map(function(sid) {
						return basicInfo.svcs[sid].shortform + ': '+basicInfo.svnum[sid];
					    },rev.svals).join(' ') + ')';
				return rev.rname+svstr;
			    },this.info.reviews).join(', ')),
			P(STRONG('Comments: '),
			    this.info.comments.length == 0 ? 'None' : 
			    map(function(c) {return c.rname;},this.info.comments).join(', '))));
	}

	this.batchCb = INPUT({type:'checkbox'});
	this.rejectDom = SPAN();
	if(rinfo.auth.role == 'admin') {
		var rejectWidget = new CheckboxWidget(this.info.rejected).serverSaving(
			function(rej) {
				return genRequest({url:'Applicant/'+me.id+'/reject',fields:{cookie:authCookie,reject:(rej?'yes':'no')},asynchronous:false});
				});
		rejectWidget.events.serverResponse.transform_e(function(sr) {
			me.info.rejected = sr.rejected;
			refilterE.sendEvent('r');
		});
		this.rejectDom = P(STRONG('Reject? '),rejectWidget.dom);
	}

	this.doms = null;
	this.getDoms = function() {
	    if (this.doms == null) {
			this.doms = [TRB(map(function(col) {return col.makeTD(me,authCookie);},cols)),this.makeSecondRow()];
	    }
	    return this.doms;
	}
	this.getObj = function() {return this;}
}

function boolCmp(a,b) { return (a == b) ? 0 : (a ? 1 : -1); };


function makeScoreCategorySelector(basicInfo) {
  var options = basicInfo.scores.map(function(score) {
    return OPTION({value: score.id.toString()}, score.shortform);
  });
  options.unshift(OPTION({value: "-1"}, "(Sort by Score)"));

  
  var avg = INPUT({type: 'checkbox'});

  var scores = SELECT.apply(this,options);
  var sortE = extractValue_e(scores);
  

  return { dom: DIV(scores,DIV(avg,'Average')), 
           sortE: merge_e(sortE,extractValue_e(avg)).calm_e(2000), 
           changeE: receiver_e() /* zero_e */,
           scoreTypeB: extractValue_b(scores),
           avgB: extractValue_b(avg)
         };
}

// false indicates that scoreId is -1 or the applicant has not been reviewed
// by the current reviewer.
function getApplicantScore(scoreId,basicInfo,reviewer,app) {
  if (!app.__personalcache) { app.__personalcache = { }; }

  if (scoreId == -1 || app.rstatus != "reviewed") {
    return false;
  }
  else if (app.__personalcache[scoreId]) {
    return app.__personalcache[scoreId];
  }
  else {
    app.__personalcache[scoreId] = app.info.reviews.ormap(function(review) { 
      return review.rname == reviewer.auth.username &&
        review.svals.ormap(function(score) {
          return basicInfo.svcs[score].id == scoreId &&
                 { score: basicInfo.svnum[score] };
        });
      }) || { score: false };
    return app.__personalcache[scoreId];
  }
}

function getAvgApplicantScore(scoreId,basicInfo,app) {
  if (!app.__avgcache) { app.__avgcache = { }; }

  if (scoreId == -1) {
    return false;
  }
  else if (app.__avgcache[scoreId]) { 
    return app.__avgcache[scoreId];
  }
  else {
    var numScores = 0;
    var netScore = app.info.reviews.foldl(0,function(acc,review) {
      var score = review.svals.ormap(function(score) {
         if (basicInfo.svcs[score].id == scoreId) { 
           numScores++; 
           return basicInfo.svnum[score];
         }
         else {
           return false;
         }
       });
       return score === false ? acc : acc + score;
    });
    app.__avgcache[scoreId]
      = numScores == 0 ? false : { score: netScore / numScores  };
    return app.__avgcache[scoreId]; 
  }
}


function getTblColumns(bi,reviewer) {
  var scoresHeader = makeScoreCategorySelector(bi);
  var scoreTypeB = scoresHeader.scoreTypeB;
  var avgB = scoresHeader.avgB;

var standardCols = [
	makeColumn('name-col','Name',function(a,b) {return a.nsorder - b.nsorder;},
		function(a,cookie) {
		    return TD(A({target:'pdf_window',href:'appreview.html?id='+a.id},a.info.name),
					P(
						A({href:'http://images.google.com/images?q='+encodeURI('"'+a.info.name+'"')},
							IMG({className:'icon',src:'images/imagesearch.png',alt:'Image Search'})),
						map(function(wc) {
							return SPAN('[',A({href:showWebsite(wc.value), target: "_blank" },wc.name),']',' ');
						},a.info.web)));
		}),
  makeColumn('info-col','Position',
    function(a,b) { return stringCmp(a.info.position,b.info.position); },
    function(a,cookie) { 
      return TD(basicInfo.positions[a.info.position].name); 
    }),
	makeColumn('info-col','Gender',function(a,b) {return stringCmp(a.info.gender,b.info.gender);},
		function(a,cookie) {return TD(a.info.gender);}),
	makeColumn('info-col','Ethnicity',function(a,b) {return stringCmp(a.info.ethnicity,b.info.ethnicity);},
		function(a,cookie) {return TD(a.info.ethname);})
];
var batchCol = makeColumn('batch','Batch?',function(a,b) {return 0;},function(a,cookie) {return TD(SPAN({className: 'batchCheckbox', style: { padding: '3px' } },a.batchCb));});

  return standardCols.concat(map(function(c) {
	 return makeColumn('statement-col',c.short,function(a,b) {return 0;},function(a,cookie) {
			return TD(a.statements[c.id] ? A({href:'Applicant/'+a.id+'/getStatement.pdf?cookie='+cookie+'&comp='+c.id},c.short) : '');});
		},bi.statements)).concat([
			makeColumn('combined-col','All',function(a,b) {return 0;},function(a,cookie) {
		    	return TD(A({href:'Applicant/'+a.id+'/getCombined.pdf?cookie='+cookie},
						(a.info.statements.length ? IMG({alt:'Get Combined PDF',title:'Get Combined PDF',border:0,src:'images/buddha.png'}) : '')));}),
    batchCol,
    makeColumn('summary', "My Scores", 
      // comparision function
      function(app1,app2) {
        var isAvg = avgB.valueNow();
        var app1s = isAvg
          ? getAvgApplicantScore(scoreTypeB.valueNow(),bi,app1)
          : getApplicantScore(scoreTypeB.valueNow(),bi,reviewer,app1);
        var app2s = isAvg
          ? getAvgApplicantScore(scoreTypeB.valueNow(),bi,app2)
          : getApplicantScore(scoreTypeB.valueNow(),bi,reviewer,app2);
        // Scores first sorted, greater first, followed by "No Score Given",
        // followed by unreviewed applicants
        if (!app1s && !app2s) { return 0; }
        else if (!app1s) { return 1; }
        else if (!app2s) { return -1; }
        else if (app2s.score === false && app2s.score === false) { return 0; }
        else if (app1s.score === false) { return 1; }
        else if (app2s.score === false) { return -1; }
        else { return app2s.score - app1s.score; }
      },
      // Display a TD containing the appropriate score for an applicant
      function (app,cookie) {
        return TDB(lift_b(function(scoreId,avg) {
          var score = !avg ? getApplicantScore(scoreId,bi,reviewer,app)
                           : getAvgApplicantScore(scoreId,bi,app);
          if (!score) { return ""; /* not reviewed */ }
          else if (score.score === false) { return "No Score Given"; }
          else { return score.score.toString(); }
        },scoreTypeB,avgB));
      },
      // Custom header that lets you choose which score to sort by
      scoresHeader)]);
}

function getTable(tblColumns,filterB,tblRowsB) {
    var hlRowsB = tblRowsB.transform_b(function(tblRows) {
	    var hlRows = []; var unhlRows = [];
	    map(function(tr) {if(tr.highlighted) hlRows.push(tr); else unhlRows.push(tr);},tblRows);
	    return [hlRows,unhlRows];
    });

    var hlw = new TableWidget(hlRowsB.lift_b(function(h) {return h[0];}),
      'applicant', tblColumns, filterB, 
      H2({style:{fontSize:'150%',marginBottom:'0.5em'}},
         'Highlighted Applicants'));

    var hld = hlw.dom;

    var nohlw = new AppTableWidget(hlRowsB.lift_b(function(h) {return h[1];}),
      'applicant', tblColumns, filterB, 
      H2({style:{fontSize:'150%',marginBottom:'0.5em'}},
      'Other Applicants'));
    var nohld = nohlw.dom;
    hld = lift_b(function(hldd,hlr) {
	    hldd.style.display = (hlr[0].length ? 'block' : 'none');
	    return hldd;
    },hld,hlRowsB);
    nohld = lift_b(function(nohldd,hlr) {
	    nohldd.getElementsByTagName('h2')[0].style.display = (hlr[0].length ? 'block' : 'none');
	    return nohldd;
    },nohld,hlRowsB);

    var batchA = A({href:'javascript:undefined'},'Create Multi-Applicant PDF');
    extractEvent_e(batchA,'click').transform_e(function(_) {
	    var wloc = 'getBatch.pdf?cookie='+authCookie;
	    var shp =  hlw.behaviors.showPapers.valueNow().concat(nohlw.behaviors.showPapers.valueNow());
      var anySelected = false;
	    map(function(ae) {
			  if(ae.batchCb.checked) { 
          anySelected = true;
          wloc += '&apps='+ae.id; ae.batchCb.checked = false; 
        }
      },shp);
      if (anySelected) { window.open(wloc); }
      else {
        highlightBatchCheckboxes();
        alert('Please select applicants to create a multi-applicant PDF.\n' +
              '(Use the checkboxes in the rightmost column.)');
      }
    });
    return DIVB({className:'applicant-list'},hld,nohld,DIVB({align:'center'},batchA));
}

var basicInfo;
  
var arrayDifferent = function(arr1, arr2) {
  if (arr1.length != arr2.length) {
    return true;
  }

  for (var i = 0; i < arr1.length; i++) {
    if (arr1[i] != arr2[i]) {
      return true;
    }
  }

  return false;
};


function loader() {
	var flapjax = flapjaxInit();
	var exceptsE = captureServerExcepts(); 
  
  // If we are not in demo mode, silently discard all notifications.
  document.notifyDemo = function(_) { };

  // hook for the demo tool.  It doesn't really "start" the demo.
  document.startDemo = function(notifyDemoCallback) {
    document.notifyDemo = notifyDemoCallback;
  };

	exceptsE.filter_e(function(_) {return _.value == 'denied';}).transform_e(function(_) {window.location='login.html?expired=true'});

	var onLoadTimeE = receiver_e();

	authCookie = getCookie('resumesession');

	var basicInfoE = getBasicInfoSE(onLoadTimeE);
  basicInfoE.lift_e(function(v) { basicInfo = parseBasic(v); });

	var curAuthE = getFilteredWSO_e(onLoadTimeE.constant_e(
		genRequest({url:'getReviewer',fields:{cookie:authCookie}})));
	
  var hiddensB = getFilteredWSO_e(
      merge_e(onLoadTimeE,timer_e(20000)).
      constant_e(genRequest({url:'getReviewer',fields:{cookie:authCookie}})))
    .collect_e({ isNew: true, value: [ ] }, function(current, prev) { 
        return { 
          isNew: arrayDifferent(prev.value,current.hiddens), 
          value: current.hiddens 
        };
      })
    .filter_e(function(v) { return v.isNew; })
    .lift_e(function(v) { return v.value; })
    .hold([]);
	
	var applicantsB = rec_e(function(aqE) {
		var lastChangeValB = aqE.transform_e(function(_) {return _.lastChange;}).startsWith(0);
		return getFilteredWSO_e(snapshot_e(
				merge_e(onLoadTimeE,timer_e(120000)),
				lastChangeValB.transform_b(function(lcv) {
				    return genRequest(
					{url:'getApplicants',
					fields:{cookie:authCookie,lastChangeVal:lcv}});
			    }))).filter_e(function(_) {return _.changed;});
		}).transform_e(function(_) {return _.value;}).startsWith([]);
	
	insertValueE(applicantsB.changes().once_e().constant_e('block'),'atbl','style','display');
	insertValueE(applicantsB.changes().once_e().constant_e('none'),'loading','style','display');

	lift_e(function(basicInfo,curAuth) {
		setHeadAndTitle(basicInfo,'Review Applicants',
			[A({href:'login.html?logout='+authCookie},'Log Out'),
			curAuth.auth.role == 'admin' ? A({href:'admin.html?cookie='+authCookie},'Admin') : '']);

		basicInfo.statements = filter(function(c) {return c.type == 'statement';},basicInfo.components);

		var tblColumns = getTblColumns(basicInfo,curAuth);

		refilterE = receiver_e();
		var tblRowsB = lift_b(function(apps) {
		    var i = 0;
		    return map(function(app) {
				i ++;
				return new ApplicantEntry(curAuth,basicInfo,app,tblColumns,i);
		    },apps);
		},applicantsB);
		tblRowsB = merge_e(tblRowsB.changes(),refilterE.snapshot_e(tblRowsB)).startsWith(tblRowsB.valueNow());
		
    pagesizecookie = getCookie('appage');
		if(!pagesizecookie) pagesizecookie = '[10,1]';
		sortcookie = getCookie('appsort');

   
    var filterFnB = initializeFilters(basicInfo, hiddensB, curAuth);
		var tableB = getTable(tblColumns,filterFnB,tblRowsB);

		insertDomB(tableB,'atbl','end');
	},basicInfoE,curAuthE);
    

	onLoadTimeE.sendEvent('Loaded!');

}

function toggleDisplay(elt,hideShowE) { 
  hideShowE.lift_e(function(isVisible) {
    elt.style.display = isVisible ? 'block': 'none';
  });
};

function grayOut(isInUse) { return isInUse ? 'black' : 'gray'; };


// [ label: string, value: string, ... ] 
// -> { element: Element, valueB: [ value, ... ] }
function checkboxList(elts,init) {
  var element = DIV();

  var ctrls = map(function(elt) { 
    var ctrl = INPUT({ type: 'checkbox', value: elt.value });
    if (init && member(elt.value,init)) { ctrl.checked = "checked" };

    element.appendChild(SPAN(ctrl,elt.label));
    return ctrl;
  }, elts);

  var getValue = function() {
    var vals = [ ];
    for (var i = 0; i < arguments.length; i++)
      { if (arguments[i]) { vals.push(elts[i].value); } }
    return vals;
  };

  var valueBs = map(function(ctrl) { return extractValue_b(ctrl); }, ctrls);

  return { element: element, 
           valueB: lift_b.apply(this,[getValue].concat(valueBs)) };
};

function nameFilter() {
  $('nameFilter').value = getCookie("nameFilter") || "";

  insertValueB($B('nameFilter').lift_b(function(name) { 
    return name ? 'black' : 'gray';
  }), $('nameFilterLabel'),'style','color');

 
  return $B('nameFilter').lift_b(function(name) {
    setCookie("nameFilter",30,name);
    return name == "" 
      ? filterNone 
      : function(applicant) {
          return applicant.info.name.toLowerCase()
                 .indexOf(name.toLowerCase()) != -1;
        };
  });
};


function areaFilter(basicInfo) {
  var initCookie = getCookie('areaFilter');
  var init = (initCookie && eval(initCookie)) || { };
  var ctrl = checkboxList(map(function(area) { 
                                return { label: area.name, value: area.id };
                              }, basicInfo.areas),init);
  // TODO: This need not be an assignment.  It should be possible to effect
  // the control itself by turning it into a behavior.
  $('filterAreaCheckboxes').appendChild(ctrl.element);


  var checked = getCookie('areaFilterType');
  if (checked) {
    $('af_' + checked).checked = "checked";
  }

  var areasB = ctrl.valueB;
  var typeB = extractValue_b('areaFilterType'); // "any" or "all"
 
  var isInUse = function(areas) { return areas.length != 0; };

  insertValueB(areasB.lift_b(isInUse).lift_b(grayOut),
    $('filterArea'), 'style', 'color');


  var filterFunction = function(areas,type) {
    setCookie('areaFilter',30,areas.toJSON());
    setCookie('areaFilterType',30,
      $$('input:checked[type="radio"][name="areaFilterType"]').pluck('value'));

    if (type == 'none') {
      document.notifyDemo({ action: "areachange" });
      return function(applicant) {
        return applicant.info.areas.length == 0;
      };
    }
    else if (areas.length == 0) {
      return filterNone;
    }
    else if (type == 'any') {
      document.notifyDemo({ action: "areachange" });
      return function(applicant) {
        for (var i = 0; i < applicant.info.areas.length; i++) {
          if (member(applicant.info.areas[i].id,areas)) { return true; }
        }
        return false;
      };
    }
    else if (type == 'all') {
      document.notifyDemo({ action: "areachange" });
      return function(applicant) {
        var applicantAreaIds = 
          map(function(area) { return area.id; }, applicant.info.areas);
             
        for (var i = 0; i < areas.length; i++) {
          if (!member(areas[i], applicantAreaIds)) { return false; }
        }
        return true;
      };
    }
    else /* something went wrong */ {
      return filterNone;
    };
  };

  return lift_b(filterFunction,areasB,typeB);
};

function letterFilter() {
  $('letterFilter').value = getCookie("letterFilter") || "";

  var rawWritersB = $B('letterFilter').calm_b(1000);
  var writersB = rawWritersB
                 .lift_b(function(str) { return str.split(/\s+/,5); })
                 .lift_b(function(pats) {
                    if (pats.length == 1 && pats[0] == "") { return [] }
                    else { return pats; }
                  });

  insertValueB(writersB.lift_b(function(v) { return v.length > 0; })
                .lift_b(grayOut), 'letterFilterSection', 'style', 'color');

  return lift_b(function(writerPatterns,rawWriters) {
    setCookie("letterFilter",30,rawWriters);
    if (writerPatterns && writerPatterns.length > 0) {
      return hasLettersBy(writerPatterns);
    }
    else {
     return filterNone;
    }
  }, writersB, rawWritersB);
};

function reviewCountFilter() {
  $('filterReviewLimit').value = getCookie("reviewCountFilter") || "";
  
  var numReviewsB = $B('filterReviewLimit').lift_b(parseInt);
	
  insertValueB(numReviewsB.lift_b(function(x) { 
		return typeof(x) == "number" && x >= 0;
	}).lift_b(grayOut),'filterNumReviewsSection','style','color');

  
  return numReviewsB.lift_b(function(x) {
    if (typeof(x) == 'number' && x >= 0) {
      setCookie('reviewCountFilter',30,x.toString());
      return function(app) {
        return app.info.reviews.length < x;
      };
    }
    else {
      setCookie('reviewCountFilter',30,"");
      return filterNone;
    }
  });
} 

function letterCountFilter() {
  $('filterLetterLimit').value = getCookie("letterCountFilter") || "";
  
  var numLettersB = 
    $B('filterLetterLimit').lift_b(parseInt);

  insertValueB(numLettersB.lift_b(function(x) { 
    return typeof(x) == "number" && x >= 0;
  }).lift_b(grayOut),'filterNumLettersSection','style','color');

  return numLettersB.lift_b(function(x) {
    if (typeof(x) == 'number' && x >= 0) {
      setCookie('letterCountFilter',30,x.toString());
      return function(app) {
        var numLetters = app.info.refletters.foldl(0,function(acc,letter) {
          return letter.submitted > 0 ? acc + 1 : acc;
        });
        return numLetters >= x;
      };
    }
    else {
      setCookie('letterCountFilter',30,"");
      return filterNone;
    }
  });
}

function hiddenFilter(basicInfo, hiddensB) {
  $('filterHidden').checked = getCookie("hiddenFilter") === "true" || false; 
 
  return lift_b(function(showHidden, hiddens) {
    setCookie("hiddenFilter",30,showHidden.toString());
    if (showHidden) { return filterNone; }
    else {
      return function(applicant) {
        return !member(applicant.id, hiddens);
      };
    }
  }, extractValue_b('filterHidden'), hiddensB);
};

function rejectedFilter() {
  $('filterRejected').checked = 
    getCookie("rejectedFilter") === "true" || false; 
  
  return extractValue_b('filterRejected').lift_b(function(showRejected) {
    setCookie("rejectedFilter",30,showRejected.toString());
    if (showRejected) { return filterNone; }
    else {
      return function(applicant) { return !applicant.info.rejected; };
    }
  });
};

function logError() {
  try {
    console.log.apply(this,arguments);
  }
  catch(_) {
    // In case of IE
  }
}

// makeTable :: (EventStream rowB) (EventStream rowB)
//           -> Behavior HTMLElement
// rowB = Behavior HTMLElement
// deleteIndex = Integer
function makeTable(style,addE, delE) {
  var addE_ = addE.lift_e(function(x) { return { addRow: x }; });
  var delE_ = delE.lift_e(function(x) { return { delElt: x }; });

  var rowsE = merge_e(addE_,delE_).collect_e([ ], function(evt, rows) {
    if (evt.addRow) {
      if (!evt.addRow.toTail) { rows.unshift(evt.addRow.value); }
      else { rows.push(evt.addRow.value); }
      return rows;
    }
    else if (evt.delElt) { 
      for (var i = 0; i < rows.length; i++) {
        if (rows[i] == evt.delElt) {
          rows.splice(i,1);
          return rows;
        }
      }
      logError("makeTable: delElt element not found", evt);
      return rows;
    }
    else {
      logError("makeTable: unexpected event", evt);
      return rows; // error is ignored.
    }
  });

  return rowsE.lift_e(function(rows) { 
           return DIVB.apply(this,[{style: style}].concat(rows)); 
         })
         .hold(DIVB())
         .switch_b();
}

function mapValues(fn,filter,obj) {
  var result = [ ];
  for (var ix in obj) { 
    if (filter(obj[ix])) { result.push(fn(obj[ix])); }
  }
  return result;
};

function makeFilterClause(basicInfo,reviewer,baseFilter) {
  var filterSelect = 
    SELECT(OPTION({ value: 'score' }, "Score"),
           OPTION({ value: 'gender' }, "Gender"),
           OPTION({ value: 'ethnicity' }, "Ethnicity"));

  var filterTypeB = extractValue_b(filterSelect);
  
  var detailsB = filterTypeB.lift_b(function(filterType) {
    if (filterType == "score") {
      var scoreCategories = basicInfo.scores.map(function(score) {
        return OPTION({value: score.id.toString()}, score.shortform);
      });
      var scoreSelect = SELECT.apply(this,scoreCategories);
      var averageCheckbox = INPUT({ type: 'checkbox', value: false});
      var boundTypeSelect = SELECT(OPTION({ value: "gt" }, "Greater Than"),
                                   OPTION({ value: "lt" }, "Less Than"),
                                   OPTION({ value: "undef" }, "Undefined"));
      var boundValueInput = INPUT({ type: 'text', size: "5" });
      var boundTypeB = extractValue_b(boundTypeSelect);

      return {
        domB: SPANB("is ",boundTypeSelect," ",
                    boundTypeB.lift_b(function(t) {
                      return t == "undef" ? "" : boundValueInput;
                    })," on ", scoreSelect," (",averageCheckbox," Average) "),
        filterB: lift_b(function(category,isAvg,type,bound) {
          if ((type == "gt" || type == "lt") && isNaN(parseInt(bound)))
            { return baseFilter; }

          bound = parseFloat(bound);

          return function(app) {
            var thisScore = isAvg 
              ? getAvgApplicantScore(parseInt(category), basicInfo, app)
              : getApplicantScore(parseInt(category), basicInfo, reviewer, app);
            var r = 
              (type == "undef" && (thisScore == false || 
                                   thisScore.score === false)) ||
              (thisScore &&
               ((type == "gt" && thisScore.score > bound) ||
               (type == "lt" && thisScore.score < bound)));
            return r;
         };
       },extractValue_b(scoreSelect),extractValue_b(averageCheckbox),
         boundTypeB,extractValue_b(boundValueInput))
      };
    }
    else if (filterType == "gender") {
      var genderSelect =
        SELECT(OPTION({ value: "none" }, "(select one)"),
               OPTION({ value: 'Male' }, "Male"),
               OPTION({ value: 'Female' }, "Female"),
               OPTION({ value: 'Unknown' }, "Unknown"));

      return {
        domB: SPANB("is ",genderSelect),
        filterB: extractValue_b(genderSelect).lift_b(function(chosenGender) {
          if (chosenGender == "none") { 
            return filterNone;
          }
          else {
            return function(app) { return app.info.gender == chosenGender; };
          }
        })
      };
    }
    else if (filterType == "ethnicity") {
      var ethnicityOptions = mapValues(
        function(eth) { return OPTION({ value: eth }, eth); },
        function(v) { return typeof(v) == "string"; },
        basicInfo.ethnicities);
      ethnicityOptions.unshift(OPTION({ value: 'none' }, "(select one)"));
      var ethnicitySelect = SELECT.apply(this,ethnicityOptions);
      return {
        domB: SPANB("is ", ethnicitySelect),
        filterB: extractValue_b(ethnicitySelect).lift_b(function(chosenEth) {
          if (chosenEth == "none") { 
            return filterNone;
          }
          else {
            return function(app) {
              return app.info.ethname == chosenEth;
            };
          }
        })
      };
    }
    else {
      logError("makeFilterClause, invalid filterType",filterType);
      return { domB: "select a filter type", filterB: constant_b(baseFilter) };
    }
  });
  
  var excludeLink = INPUT({ type: 'checkbox' });
  var maybeInvert = function(filterB) {
    return lift_b(function(filterFn,invert) {
      return (!invert) 
        ? filterFn
        : (filterFn == filterNone 
             ? filterAll 
             : (filterFn == filterAll
                  ? filterSome
                  : function(v) { return !filterFn(v); }));
    }, filterB, extractValue_b(excludeLink));
  };

  // Filter-independent layout
  var deleteLink = A({ href: "javascript:undefined" }, "[-]");
  return {
    domB: DIVB({ style: { padding: '3px' } },filterSelect," ",
               detailsB.lift_b(function(obj) { return obj.domB; }).switch_b(),
               " (",excludeLink,"Invert Matches) ",deleteLink),
    deleteE: clicks_e(deleteLink),
    filterB: maybeInvert(detailsB.lift_b(function(obj) { return obj.filterB; })
                                 .switch_b())
  };
};

var one_e = function(val) {
  var e = receiver_e();
  window.setTimeout(function() { e.sendEvent(val); },0);
  return e;
};

function makeScoreFilterDisjunction(basicInfo,reviewer) {
  var deleteE = receiver_e();

  var numFilters = 0;

  var filters = [ ];
  var filterUpdate = receiver_e();
  var newAtomA = A({href: 'javascript:undefined'}, "or...");

  var deleteThisDisjunctE = receiver_e();
  var newAtomE = clicks_e(newAtomA);

  var insertE = merge_e(newAtomE,one_e(true)).lift_e(function(_) {
    // Filtering out everything is the identity of an or-clause
    var scoreFilter = makeFilterClause(basicInfo,reviewer,filterAll);
    numFilters++;
    filters.push(scoreFilter.filterB);
    filterUpdate.sendEvent(filters);
    scoreFilter.deleteE.lift_e(function(_) {
      numFilters--;
      for (var i = 0; i < filters.length; i++) {
        if (filters[i] == scoreFilter.filterB) {
          filters.splice(i,1);
          break;
        }
      }
      // silent failure if the filter is not found
      filterUpdate.sendEvent(filters);

      deleteE.sendEvent(scoreFilter.domB);
    });
    return { value: scoreFilter.domB };
  });

  var domB = makeTable({ border: "1px solid gray", margin: "3px", 
                         padding: "3px" }, 
                       merge_e(insertE,
                               one_e({ value: newAtomA, toTail: true })),
                       deleteE);
  
  return {
    domB: domB,
    deleteE: filterUpdate.filter_e(function(clauses) { 
      return clauses.length == 0; 
    }),
    filterB: filterUpdate
    .lift_e(function(args) {
         return lift_b.apply(this,[orFilters].concat(filters));
     })
     .hold(constant_b(filterNone)).switch_b()
  };
};

// Construct a table of score filters.
function makeScoreFilterCNF(basicInfo, reviewer) {

  var deleteE = receiver_e();

  var numFilters = 0;

  var filters = [ ];
  var filterUpdate = receiver_e();

  // A conjunction of disjunctions.  Clicking the "and.." button creates
  // a new or-clause which is added to the larger and-clause.
  var newDisjunctA = A({href:'javascript:undefined'},"and...");
            
  // add a blank disjunct when all are cleared
  var onClearedE = 
    filterUpdate.filter_e(function(args) { return args.length == 0; });
  
  var insertE = merge_e(clicks_e(newDisjunctA),
                        onClearedE,one_e(true)).lift_e(function(_) {
    var scoreFilter = makeScoreFilterDisjunction(basicInfo,reviewer);
    numFilters++;
    filters.push(scoreFilter.filterB);
    filterUpdate.sendEvent(filters);
    scoreFilter.deleteE.lift_e(function(_) {
      numFilters--;
      for (var i = 0; i < filters.length; i++) {
        if (filters[i] == scoreFilter.filterB) {
          filters.splice(i,1);
          break;
        }
      }
      // silent failure if the filter is not found
      filterUpdate.sendEvent(filters);

      deleteE.sendEvent(scoreFilter.domB);
    });
    return { value: scoreFilter.domB };
  });
  
  var domB = makeTable({},
    merge_e(insertE,
            one_e({ value: newDisjunctA, toTail: true })),
    deleteE);

  var result =  filterUpdate
          .lift_e(function(args) {
             return lift_b.apply(this,[joinFilters].concat(filters));
           })
          .hold(constant_b(filterNone)).switch_b();
  
  insertDomB(domB,$('filterScore')); 
  return result;
} 

var makeScoreFilters = makeScoreFilterCNF;

function reviewFilter(basicInfo) {
  $('filterReviewer').value = getCookie('filterReviewer') || "";
  $('filterReviewType').value = getCookie('filterReviewType') || "none";
 
  // "review", "comment", "noreview" or undefined
  var typeB = extractValue_b('filterReviewType');
  var reviewerRawB = extractValue_b('filterReviewer');
  var reviewerB = reviewerRawB
                  .lift_b(function(str) { return str && str.split(/\s+/,10); })
                  .lift_b(function(pats) {
                    if (pats.length == 1 && pats[0] == "") { return [] }
                    else { return pats; }
                  });

  insertValueB(lift_b(function(type,reviewer) {
                        return type != 'none' && reviewer.length > 0; },
                      typeB,reviewerB)
               .lift_b(grayOut),
               'filterReviewSection', 'style', 'color');



  var filterFn = function(type,reviewers,reviewersRaw) {
    setCookie('filterReviewType',30,type);
    setCookie('filterReviewer',30,reviewersRaw);
    
    if (!type || reviewers.length == 0) {
      return filterNone;
    }


    return function(applicant) {
      return reviewers.ormap(function(reviewer) {
        if (reviewer == 'me') {
          return (applicant.rstatus == "comment" && type == "comment") ||
                 (applicant.rstatus == "review" && type == "review") ||
                 (applicant.rstatus == "none" && type == "noreview");
        }
        else if (type == "comment") {
          return applicant.info.comments.ormap(function(comment) {
            return comment.rname == reviewer;
          });
        }
        else if (type == "review") {
          return applicant.info.reviews.ormap(function(review) {
            return review.rname == reviewer;
          });
        }
        else if (type == "noreview") {
          return !applicant.info.comments.ormap(function(comment) {
            return comment.rname == reviewer;
          }) && !applicant.info.reviews.ormap(function(review) {
            return review.rname == reviewer;
          });
        }
        else /* something went wrong, skip this filter */ {
          return true;
        }
      });
    };
  };

  return lift_b(filterFn,typeB,reviewerB,reviewerRawB); 
}

// If the filter is not active, return filterNone.  This skips the filter
// entirely from the filter-chain.
function filterNone(_) { return true; };

function filterAll(_) { return false; }

function orFilters() {
  // Usability: A single blank clause in an or block will not filter out
  // everything.
  if (arguments.length == 1 && arguments[0] == filterAll) {
    return filterNone;
  }
  else {
    return fold(function(fn,acc) {
      return fn == filterAll ? acc : orFilter(fn,acc);
   },filterAll,arguments);
  }
}

function joinFilters() {
  return fold(function(fn,acc) { 
                return fn == filterNone ? acc : composeFilters(fn,acc);
              }, filterNone, arguments);
};

function makeWithFilter(basicInfo,elt,componentId) {

  var id;
  for (var i = 0; i < basicInfo.statements.length; i++) {
    if (basicInfo.statements[i].name == componentId) { 
      id = basicInfo.statements[i].id;
      break; 
    }
  }
  if (id == undefined) {
    errorLog("makeWithFilter: could not find component", componentId,basicInfo);
  }

  return extractValue_b(elt).lift_b(function (isActive) {
    return isActive
      ? function(app) { return !!(app.statements[id]); }
      : filterNone;
  });
}



function initializeFilters(basicInfo, hiddensB, reviewer) {
  toggleDisplay($('allFilters'),
    clicks_e($('toggleFilters')) // TODO: + / - text
    .collect_e(false,function(_,prev) { 
       document.notifyDemo({ action: 'filtertoggle' });
       return !prev; }));

  var f = lift_b.apply(this,
    [ joinFilters, nameFilter(), 
      areaFilter(basicInfo),
      reviewFilter(basicInfo),
      letterFilter(),
      makeScoreFilters(basicInfo, reviewer),
      makeWithFilter(basicInfo, "filterTS", "Teaching Statement"),
      makeWithFilter(basicInfo, "filterCL", "Cover Letter"),
      makeWithFilter(basicInfo, "filterCV", "Curriculum Vitae"),
      makeWithFilter(basicInfo, "filterRS", "Research Statement"),
      rejectedFilter(),
      letterCountFilter(),
      reviewCountFilter(),
      hiddenFilter(basicInfo, hiddensB)]);


  return f.calm_b(2000); // 2-second delay between filter updates
};

