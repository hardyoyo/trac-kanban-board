var kanban = kanban || {};

kanban.Ticket = function(data) {
    console.log('new Ticket' + data.id);
    var self = this;
    this.id = data.id;
    this.summary = ko.observable(data.summary);
    this.status = ko.observable(data.status);
    this.priority = data.priority;
    this.type = data.type;
    this.href = data.href;
    this.time = kanbanutil.timestampToDate(data.time);
    this.changetime = ko.observable(kanbanutil.timestampToDate(data.changetime));
    this.modified = false;
    this.idString = ko.computed(function() {
        return '#' + self.id;
    });

    this.viewDetails = function(ticket, event) {
        kanban.rootModel.pickedTicket(ticket);
        kanban.ticketDialog = $('#ticketDialog').dialog({
            modal: true,
            title: 'Ticket ' + ticket.idString(),
            minWidth: 400
        });
    }
};

/*
    Serialize Ticket object.
    If ticket has been modified, serialization includes all properties. If not, only id is included.
*/
kanban.Ticket.prototype.toJSON = function() {
    if (!this.modified) {
        return { id: this.id };
    }
    var copy = ko.toJS(this);
    delete copy.time;
    delete copy.changetime;
    delete copy.modified;
    delete copy.idString;
    return copy;
};

kanban.Column = function(data) {
    console.log('new Column: ' + data.id);
    var self = this;
    this.id = data.id;
    this.name = data.name;
    this.wip = ko.observable(data.wip);
    this.states = data.states;
    this.tickets = ko.observableArray($.map(data.tickets, function(i) { return new kanban.Ticket(i); }));
    this.tickets.id = data.id; // needed in sortable.afterMove function to find out source and target columns
};

kanban.Board = function(columns) {
    console.log('new Board');
    var self = this;
    this.columns = ko.observableArray($.map(columns, function(i) { return new kanban.Column(i); }));
    this.pickedTicket = ko.observable();

    this.columnWidth = ko.computed(function() {
        return Math.floor(100 / self.columns().length) + '%';
    }, this);

    /* Called when card has been dragged to new position. */
    this.afterMove = function(arg) {
        console.log(arg);
        var modifiedColumns = [self.getColumn(arg.sourceParent.id)];

        var targetColumn = self.getColumn(arg.targetParent.id);
        if (arg.sourceParent.id != arg.targetParent.id) {
            // Ticket's new status is the first mapped status of the column
            arg.item.status(targetColumn.states[0]);
            arg.item.modified = true;
            arg.item.changetime(new Date());
            modifiedColumns.push(targetColumn);
        }

        kanban.request(
            kanban.DATA_URL,
            'POST',
            ko.toJSON(modifiedColumns),
            function(data) {console.log("updated");},
            function() {console.log("update error")});

        arg.item.modified = false;
    };

    this.getColumn = function(id) {
        var cols = self.columns();
        for (var i in cols) {
            if (cols[i].id == id) return cols[i];
        }
        return null;
    };
};

kanban.request = function(url, type, reqData, onSuccess, onError) {
    $.ajax({
        type: type,
        url: url,
        contentType: 'application/json',
        data: reqData,
        dataType: 'json',
        success: onSuccess,
        error: onError
    });
};

kanban.onDataFetched = function(data) {
    console.log(data);
    kanban.rootModel = new kanban.Board(data);
    ko.bindingHandlers.sortable.isEnabled = IS_EDITABLE;
    ko.bindingHandlers.sortable.afterMove = kanban.rootModel.afterMove;
    ko.bindingHandlers.sortable.options = {
        placeholder: 'kanban-card-placeholder',
        forcePlaceholderSize: true,
        opacity: 0.5
    };
    ko.applyBindings(kanban.rootModel);
};

kanban.onDataFetchError = function(jqXHR, textStatus, error) {
    $('.kanban-column-container').html('<h2>' + textStatus + '</h2>');
};

$(document).ready(function(){
    console.log("Document ready. Board ID: " + KANBAN_BOARD_ID + ", " + (IS_EDITABLE ? "editable" : "read-only"));

    kanban.DATA_URL = '/' + TRAC_PROJECT_NAME + '/kanbanboard/' + KANBAN_BOARD_ID;
    kanban.request(
        kanban.DATA_URL,
        'GET',
        null,
        kanban.onDataFetched,
        kanban.onDataFetchError);
});
