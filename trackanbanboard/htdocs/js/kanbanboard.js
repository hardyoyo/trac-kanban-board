var kanban = kanban || {};

kanban.Ticket = function(data) {
    var self = this;

    ko.mapping.fromJS(data, {
        copy: ['id']
    }, this);

    this.comment = ko.observable('');

    this.idString = ko.computed(function() {
        if (self.id)
            return '#' + self.id;
        return '';
    });

    this.link = ko.computed(function() {
        if (self.id)
            return '/' + TRAC_PROJECT_NAME + '/ticket/' + self.id;
        return '#';
    });

    this.fieldOptions = function(fieldName) {
        var currentValue = self[fieldName]();
        var optionList = [];

        if (kanban.metadata && kanban.metadata.ticketFields) {
            for (var i in kanban.metadata.ticketFields) {
                if (kanban.metadata.ticketFields[i].name == fieldName &&
                    kanban.metadata.ticketFields[i].options) {

                    optionList = kanban.metadata.ticketFields[i].options.slice(0);
                    if (kanban.metadata.ticketFields[i].optional && fieldName != 'status') {
                        optionList.unshift('');
                    }
                    break;
                }
            }
        }

        var valueInList = false;
        for (var j in optionList) {
            if (optionList[j] == currentValue)
                valueInList = true;
        }
        if (!valueInList)
            optionList.unshift(currentValue);

        return optionList;
    };

    this.modifiedFields = [];
    this.setField = function(fieldName, value) {
        self[fieldName](value);
        self.modifiedFields.push(fieldName);
        if (self.changetime) {
            self.changetime(new Date().getTime());
        }
    };

    this.updateData = function(data) {
        ko.mapping.fromJS(data, self);

        if (kanban.rootModel) {
            var dt = kanban.rootModel.dialogTicket();
            if (dt && dt.id == self.id) {
                kanban.rootModel.selectedTicket(self);
                kanban.rootModel.dialogTicket(new kanban.Ticket(ko.mapping.toJS(self)));
            }
        }
    };
};

/*
    Serialize Ticket object. Only id and modified fields are included.
*/
kanban.Ticket.prototype.toJSON = function() {
    var obj = { id: this.id };
    for (var i in this.modifiedFields) {
        var fieldName = this.modifiedFields[i];
        obj[fieldName] = this[fieldName];
    }
    return obj;
};

kanban.Column = function(data) {
    var self = this;

    ko.mapping.fromJS(data, {
        copy: ['id', 'states'],
        'tickets': {
            key: function(ticketData) { return ko.utils.unwrapObservable(ticketData.id); },
            create: function(options) { return new kanban.Ticket(options.data); },
            update: function(options) {
                options.target.updateData(options.data);
                return options.target;
            }
        }
    }, this);

    this.tickets.id = data.id; // needed in sortable.afterMove function to find out source and target columns
    this.modifiedFields = [];

    this.updateData = function(data) {
        ko.mapping.fromJS(data, self);
    };
};

/*
 Serialize Column object. Only id and modified fields are included.
 */
kanban.Column.prototype.toJSON = function() {
    var obj = { id: this.id };
    for (var i in this.modifiedFields) {
        var fieldName = this.modifiedFields[i];
        obj[fieldName] = this[fieldName];
    }
    return obj;
};

kanban.Board = function(data) {
    var self = this;

    this.mapping = {
        'columns': {
            key: function(coldata) { return ko.utils.unwrapObservable(coldata.id); },
            create: function(options) { return new kanban.Column(options.data); },
            update: function(options) {
                options.target.updateData(options.data);
                return options.target;
            }
        }
    };

    ko.mapping.fromJS(data, this.mapping, this);

    /* The ticket clicked by user. */
    this.selectedTicket = ko.observable(null);
    /* The ticket displayed in ticket detail dialog. This is initially copy of selected ticket. */
    this.dialogTicket = ko.observable(null);

    /* Accepted values for various ticket fields. Keys are field names and values are observable arrays of strings.
       For example: { 'type': ko.observableArray(['defect, 'enhancement', 'task']) }*/
    this.ticketFieldOptions = {};

    this.setTicketFieldOptions = function(fieldName, options) {
        // Add the "not defined" option.
        // Trac defines status to be optional but kanban board requires it to be always set.
        for (var i in kanban.metadata.ticketFields) {
            if (fieldName != 'status' &&
                fieldName == kanban.metadata.ticketFields[i].name &&
                kanban.metadata.ticketFields[i].optional) {
                options.unshift('');
            }
        }

        self.ticketFieldOptions[fieldName] = ko.observableArray(options);
    };

    this.columnWidth = ko.computed(function() {
        return 100 / self.columns().length + '%';
    }, this);

    /* Called when card has been dragged to new position. */
    this.afterMove = function(arg) {
        var sourceColumn = self.getColumn(arg.sourceParent.id);
        sourceColumn.modifiedFields.push('tickets');
        var modifiedColumns = [sourceColumn];

        var targetColumn = self.getColumn(arg.targetParent.id);
        if (arg.sourceParent.id != arg.targetParent.id) {
            // Ticket's new status is the first mapped status of the column
            arg.item.setField('status', targetColumn.states[0]);
            targetColumn.modifiedFields.push('tickets');
            modifiedColumns.push(targetColumn);
        }

        kanban.request(
            kanban.DATA_URL,
            'POST',
            ko.toJSON(modifiedColumns),
            function(data) {
                self.updateData(data);
            },
            function() {
                console.error("update error");
            });

        arg.item.modifiedFields = [];
        for (var i in modifiedColumns) {
            modifiedColumns[i].modifiedFields = [];
        }
    };

    /* Get column with ID 'id' */
    this.getColumn = function(id) {
        return ko.utils.arrayFirst(self.columns(), function(item) {
            return item.id == id;
        });
    };

    /* Get column which contains ticket with ID 'ticketId' */
    this.getTicketColumn = function(ticketId) {
        var cols = self.columns();
        for (var i in cols) {
            var col = cols[i];
            for (var j in col.tickets()) {
                var ticket = col.tickets()[j];
                if (ticket.id == ticketId) return cols[i];
            }
        }
        return null;
    };

    /* Get user friendly label for ticket field. */
    this.fieldLabel = function(fieldName) {
        for (var i in kanban.metadata.ticketFields) {
            if (kanban.metadata.ticketFields[i].name == fieldName) {
                return kanban.metadata.ticketFields[i].label;
            }
        }
        return "ERROR";
    };

    this.updateData = function(data) {
        console.log('Update board', data);
        ko.mapping.fromJS(data, self);
    };

    this.selectTicket = function(ticket) {
        self.selectedTicket(ticket);
        /* Use copy of selected ticket in dialog so that original ticket doesn't change before Save is clicked. */
        self.dialogTicket(new kanban.Ticket(ko.mapping.toJS(ticket)));
        self.showTicketDialog();
        self.fetchData([ ticket.id ]);
    };

    this.createTicket = function() {
        var defaultData = kanban.getNewTicketData();
        self.dialogTicket(new kanban.Ticket(defaultData));
        self.showTicketDialog();
    };

    /* Fetch board data from backend. Data includes all columns and all tickets. By default ticket data includes
        only id, summary and status fields. For tickets specified in detailedTickets argument, all fields are included. */
    this.fetchData = function(detailedTickets) {
        var args = '';
        if (detailedTickets && Object.prototype.toString.call(detailedTickets) === '[object Array]') {
            args = '?detailed=' + detailedTickets.join(',');
        }
        var url = kanban.DATA_URL + args;
        kanban.request(
            url,
            'GET',
            null,
            self.updateData,
            function() {
                console.error('Failed to fetch board data');
            });
    };

    this.showTicketDialog = function() {
        var newTicket = typeof self.dialogTicket().id === 'undefined';
        var buttons = {};

        if (IS_EDITABLE) {
            if (!newTicket) {
                buttons['Remove from board'] = function() {
                    self.removeTicket(self.selectedTicket().id);
                    $(this).dialog("close");
                };
                buttons['Save'] = function() {
                    self.saveDialogTicket(self.selectedTicket());
                    $(this).dialog("close");
                };
            } else {
                buttons['Create'] = function() {
                    self.createDialogTicket();
                    $(this).dialog("close");
                };
            }
        }
        buttons['Cancel'] = function() { $(this).dialog("close"); };

        var $dialogDiv = $('#ticketDialog');
        if (newTicket)
            var titleString = 'New ticket';
        else
            var titleString = '<a href="' + self.dialogTicket().link() + '">Ticket ' + self.dialogTicket().idString() + '</a>';

        kanban.ticketDialog = $dialogDiv.dialog({
            modal: true,
            title: titleString,
            minWidth: 600,
            buttons: buttons
        });
    };

    this.showQueryDialog = function() {
        var $iframe = $('#queryFrame');
        $iframe.off('load');
        $iframe.on('load', function () {
            var $banner = $iframe.contents().find('#banner');
            if ($banner) $banner.hide();
            var $mainnav = $iframe.contents().find('#mainnav');
            if ($mainnav) $mainnav.hide();
        });

        $iframe.attr('src', kanban.QUERY_URL);
        var $dialogDiv = $('#queryDialog');
        kanban.queryDialog = $dialogDiv.dialog({
            title: 'Drag and drop ticket links to Kanban board',
            width: 600,
            height: 400,
            position: 'right'
        });

        // Workaround for http://bugs.jqueryui.com/ticket/7650
        kanban.queryDialog.off('dialogresizestart');
        kanban.queryDialog.on('dialogresizestart', self.createQueryDialogOverlay);

        kanban.queryDialog.off('dialogresizestop');
        kanban.queryDialog.on('dialogresizestop', self.destroyQueryDialogOverlay);

        kanban.queryDialog.off('dialogdragstart');
        kanban.queryDialog.on('dialogdragstart', self.createQueryDialogOverlay);

        kanban.queryDialog.off('dialogdragstop');
        kanban.queryDialog.on('dialogdragstop', self.destroyQueryDialogOverlay);
    };

    this.createQueryDialogOverlay = function() {
        var $iframe = $('#queryFrame');
        var $d = $('<div></div>');
        $iframe.after($d[0]);
        $d[0].id = 'tempDiv';
        $d.css({position: 'absolute'});
        $d.css({top: $iframe.position().top, left: 0});
        $d.height($iframe.height());
        $d.width('100%');
    };

    this.destroyQueryDialogOverlay = function() {
        $('#tempDiv').remove();
    };

    /* Check if dialog ticket has changed from original ticket and save changes if necessary */
    this.saveDialogTicket = function(originalTicket) {
        var modified = false;

        for (var i in kanban.metadata.ticketFields) {
            var fieldName = kanban.metadata.ticketFields[i].name;
            if (fieldName == 'time' || fieldName == 'changetime') continue;
            if (self.dialogTicket()[fieldName] &&
                self.dialogTicket()[fieldName]() != originalTicket[fieldName]()) {
                originalTicket.setField(fieldName, self.dialogTicket()[fieldName]());
                modified = true;
            }
        }

        if (self.dialogTicket().comment) {
            originalTicket.setField('comment', self.dialogTicket().comment);
            modified = true;
        }

        if (modified) {
            kanban.request(
                kanban.TICKET_URL,
                'POST',
                ko.toJSON(originalTicket),
                function(data) {
                    self.updateData(data);
                },
                function() {
                    console.error("update error");
                });

            originalTicket.modifiedFields = [];
            originalTicket.comment('');
        }
    };

    this.createDialogTicket = function() {
        var fieldNames = [];
        for (var i in kanban.metadata.ticketFields) {
            var name = kanban.metadata.ticketFields[i].name;
            if (name != 'time' && name != 'changetime')
                fieldNames.push(name);
        }
        self.dialogTicket().modifiedFields = fieldNames;

        kanban.request(
            kanban.TICKET_URL,
            'POST',
            ko.toJSON(self.dialogTicket()),
            function(data) {
                self.updateData(data);
            },
            function() {
                console.error("create error");
            });

        self.dialogTicket().modifiedFields = [];
    };

    this.addTicket = function(ticketId) {
        var url = kanban.DATA_URL + '?add=' + ticketId;
        kanban.request(
            url,
            'GET',
            null,
            function(data) {
                self.updateData(data);
            },
            function() {
                console.error("adding error");
            });
    };

    this.removeTicket = function(ticketId) {
        var url = kanban.DATA_URL + '?remove=' + ticketId;
        kanban.request(
            url,
            'GET',
            null,
            function(data) {
                self.updateData(data);
            },
            function() {
                console.error("removing error");
            });
    };

    /* Toggles ticket detail dialog section (description, changelog, comment) visibility*/
    this.toggleSection = function(data, event) {
        $(event.target).siblings('.section-content').slideToggle(300);
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
    console.log('Board data fetched:', data);
    kanban.rootModel = new kanban.Board(data);

    ko.bindingHandlers.sortable.isEnabled = IS_EDITABLE;
    ko.bindingHandlers.sortable.afterMove = kanban.rootModel.afterMove;
    ko.bindingHandlers.sortable.options = {
        placeholder: 'kanban-card-placeholder',
        forcePlaceholderSize: true,
        opacity: 0.5
    };
    ko.applyBindings(kanban.rootModel);

    $('.board-container').on('dragover', function(e) {
        if (IS_EDITABLE) {
            // Default dragover behaviour must be canceled or else drop event is never fired
            e.stopPropagation();
            e.preventDefault();
            return false;
        }
        return true
    }).on('drop', function(e) {
        if (IS_EDITABLE) {
            e.stopPropagation();
            e.preventDefault();
            var id = kanbanutil.getTicketIdFromDropEvent(e, TRAC_PROJECT_NAME);
            if (id) {
                kanban.rootModel.addTicket(id);
            }
            return false;
        }
        return true
    });
};

kanban.onDataFetchError = function(jqXHR, textStatus, error) {
    $('.kanban-column-container').html('<h2>' + textStatus + '</h2>');
};

$(document).ready(function(){
    console.log(
        "Board ID:", KANBAN_BOARD_ID,
        "; Project name:", TRAC_PROJECT_NAME,
        "; User name:", TRAC_USER_NAME,
        (IS_EDITABLE ? "; Editable" : "; Read-only"),
        "; Ticket fields:", TICKET_FIELDS);

    kanban.DATA_URL = '/' + TRAC_PROJECT_NAME + '/kanbanboard/' + KANBAN_BOARD_ID;
    kanban.QUERY_URL = '/' + TRAC_PROJECT_NAME + '/query?status=new&col=id&col=summary&col=status&col=type&col=priority&order=id';
    kanban.TICKET_URL = kanban.DATA_URL + '/ticket';

    $('.board-container .toolbar button').button();

    kanban.request(
        '/' + TRAC_PROJECT_NAME + '/kanbanboard/',
        'GET',
        null,
        function(data) {
            kanban.metadata = data;

            if (TICKET_FIELDS && data && data.ticketFields) {
                kanban.createTicketFields($('.field-table'), TICKET_FIELDS, data.ticketFields);
            }

            kanban.request(
                kanban.DATA_URL,
                'GET',
                null,
                kanban.onDataFetched,
                kanban.onDataFetchError);
        },
        function() {
            console.error('Failed to fetch project metadata');
        }
    );
});

/* Add user defined ticket fields to detail dialog template. */
kanban.createTicketFields = function($table, fieldString, validFields) {
    fieldList = fieldString.split(',');

    var html = [];
    for (var i in fieldList) {
        var fieldName = fieldList[i];
        var fieldDef = null;
        for (var j in validFields) {
            if (validFields[j].name == fieldName) fieldDef = validFields[j];
        }
        if (!fieldDef) {
            console.error('Invalid field:', fieldName);
            continue;
        }

        if (i % 2 == 0) {
            html.push('<tr>');
        }

        html.push('<td>');
        html.push('<span data-bind="text: $root.fieldLabel(\'');
        html.push(fieldName);
        html.push('\')">&nbsp;</span>');
        html.push('</td>');

        html.push('<td data-bind="if: typeof $data.');
        html.push(fieldName);
        html.push(' !== \'undefined\'">');

        switch (fieldDef.type) {
            case 'text':
            case 'textarea':
                html.push('<input type="text" data-bind="enable: IS_EDITABLE, value: ');
                html.push(fieldName);
                html.push('" />');
                break;

            case 'select':
            case 'radio':
                html.push('<select data-bind="enable: IS_EDITABLE, value: ');
                html.push(fieldName);
                html.push(', options: fieldOptions(\'');
                html.push(fieldName);
                html.push('\')">&nbsp;</select>');
                break;
        }

        html.push('</td>');

        if (i % 2 == 1) {
            html.push('</tr>');
        }
    }
    $table.append(html.join(''));
};

kanban.getNewTicketData = function() {
    var data = {};
    if (kanban.metadata && kanban.metadata.ticketFields) {
        for (var i in kanban.metadata.ticketFields) {
            var field = kanban.metadata.ticketFields[i];
            var value;
            switch (field.type) {
                case 'text':
                case 'textarea':
                    value = '';
                    break;
                case 'select':
                case 'radio':
                    value = field.value;
                    break;
            }
            if (field.name === 'status')
                value = 'new';
            if (field.name === 'owner')
                value = 'somebody';
            if (field.name === 'reporter')
                value = TRAC_USER_NAME;
            if (field.name === 'resolution')
                value = '';

            if (typeof value !== 'undefined')
                data[field.name] = value;
        }
    }
    return data;
}
