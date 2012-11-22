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
