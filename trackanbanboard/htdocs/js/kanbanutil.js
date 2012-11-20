var kanbanutil = kanbanutil || {};

// Prepend number with zeros until it is 'width' digits long.
// Example: zeroFill(7, 3) returns '007'
kanbanutil.zeroFill = function(number, width) {
    width -= number.toString().length;
    if (width > 0) {
        return new Array(width + (/\./.test(number) ? 2 : 1)).join('0') + number;
    }
    return number;
};

kanbanutil.timestampToDate = function(timestamp) {
    return new Date(timestamp * 1000);
};

kanbanutil.dateToTimestamp = function(date) {
    return Math.round(date.getTime() / 1000);
};

ko.bindingHandlers.readableDate = {
    update: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var date = ko.utils.unwrapObservable(valueAccessor());
        var text = [date.toDateString()];
        text.push(' &ndash; ');
        text.push(kanbanutil.zeroFill(date.getHours(), 2));
        text.push(':');
        text.push(kanbanutil.zeroFill(date.getMinutes(), 2));
        $(element).html(text.join(''));
    }
};
