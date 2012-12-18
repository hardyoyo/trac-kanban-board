var kanbanutil = kanbanutil || {};

/* Prepend number with zeros until it is 'width' digits long.
 * Example: zeroFill(7, 3) returns '007' */
kanbanutil.zeroFill = function(number, width) {
    width -= number.toString().length;
    if (width > 0) {
        return new Array(width + (/\./.test(number) ? 2 : 1)).join('0') + number;
    }
    return number;
};

/*
 * If element dropped in 'event' is a ticket link for project 'projectName', return the ticket ID.
 */
kanbanutil.getTicketIdFromDropEvent = function(event, projectName) {
    var dataTransfer;
    var url;
    var id;
    if (event && event.dataTransfer) {
        dataTransfer = event.dataTransfer;
    } else if (event && event.originalEvent && event.originalEvent.dataTransfer) {
        dataTransfer = event.originalEvent.dataTransfer;
    }

    if (dataTransfer) {
        if (dataTransfer.types) {
            for (var i in dataTransfer.types) {
                if (dataTransfer.types[i] === 'text/uri-list') {
                    url = dataTransfer.getData(dataTransfer.types[i]);
                }
            }
        } else {
            url = dataTransfer.getData('Text');
        }
    }

    if (url) {
        var re = new RegExp('\\/' + projectName + '\\/ticket\\/(\\d+)');
        var match = url.match(re);
        if (match && match.length == 2) {
            id = parseInt(match[1]);
        }
    }
    return id;
};

/* Knockout.js binding for displaying timestamp in human readable form */
ko.bindingHandlers.readableDate = {
    update: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var date = new Date(ko.utils.unwrapObservable(valueAccessor()));
        var text = ['<span>'];
        text.push(date.toDateString());
        text.push(' &ndash; ');
        text.push(kanbanutil.zeroFill(date.getHours(), 2));
        text.push(':');
        text.push(kanbanutil.zeroFill(date.getMinutes(), 2));
        text.push('</span>');
        $(element).html(text.join(''));
    }
};

/* Knockout.js binding for displaying ticket changelog entry */
ko.bindingHandlers.changelogEntry = {
    update: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var changeList = ko.utils.unwrapObservable(valueAccessor());
        var comment = '';
        var html = [];
        for (var i in changeList) {
            if (changeList[i].field() == 'comment') {
                comment = changeList[i].newValue();
            } else {
                html.push('<div class="log-change">');
                html.push('<span class="log-field">');
                html.push(changeList[i].field());
                html.push('</span>');

                if (changeList[i].field() == 'description') {
                    html.push('&nbsp;modified');
                } else {
                    html.push('&nbsp;changed&nbsp;from&nbsp;');
                    html.push('<span class="log-value">');
                    html.push(changeList[i].oldValue());
                    html.push('</span>');
                    html.push('&nbsp;to&nbsp;');
                    html.push('<span class="log-value">');
                    html.push(changeList[i].newValue());
                    html.push('</span>');
                }
                html.push('</div>');
            }
        }
        if (comment) {
            html.push('<div class="log-comment">');
            html.push(comment);
            html.push('</div>');
        }
        $(element).html(html.join(''));
    }
};
