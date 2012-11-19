var kanbanutil = kanbanutil || {};

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
        text.push(' ');
        text.push(date.getHours());
        text.push(':');
        text.push(date.getMinutes());
        $(element).html(text.join(''));
    }
};
