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
    console.log('getTicketIdFromDropEvent', event);

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
        console.log('re:', re.source);
        var match = url.match(re);
        console.log(match);

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
        var text = ['<span class="date-time">'];
        text.push(date.toDateString());
        text.push(' &ndash; ');
        text.push(kanbanutil.zeroFill(date.getHours(), 2));
        text.push(':');
        text.push(kanbanutil.zeroFill(date.getMinutes(), 2));
        text.push('</span>');
        $(element).html(text.join(''));
    }
};
