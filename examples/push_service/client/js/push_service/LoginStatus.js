define
  ( [ 'dojo/_base/declare'
    , 'dojo/_base/config'
    , 'app/util'
    , 'dojo/on'
    , 'dijit/_WidgetBase'
    , 'dijit/_TemplatedMixin'
    , 'dijit/_WidgetsInTemplateMixin'
    , 'dojo/text!app/view/login_status.html'
    , 'dijit/form/Button'
    ]
    , function( declare, config, util, on, Widget, Templated, WidgetsInTemplate, template  ) {

        return declare
          ( 'app.LoginStatus'
          , [ Widget, Templated, WidgetsInTemplate ]
          , { templateString: template
            , postCreate: function() {
                this.inherited( arguments );
                this.watcher = util.bind( config.app.userManager, "current", this, "user" );
                on( this.logoutButton, "click", function() {
                  config.app.remoteApi.logout();
                });
              }
            , _setUserAttr: function( user ) {
                if (this.name)
                  this.name.innerHTML = user.name;
              }
            , destroy: function( ) {
                if (this.watcher)
                  this.watcher.cancel();
                this.inherited( arguments );
              }
            }
          );
    });

