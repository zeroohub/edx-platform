/* eslint-disable no-underscore-dangle */
(function(define) {
    'use strict';

    define([
        'gettext',
        'jquery',
        'underscore',
        'backbone',
        'edx-ui-toolkit/js/utils/string-utils',
        'edx-ui-toolkit/js/utils/html-utils',
        'js/views/fields',
        'js/views/image_field',
        'text!learner_profile/templates/social_icons.underscore',
        'backbone-super'
    ], function(gettext, $, _, Backbone, StringUtils, HtmlUtils, FieldViews, ImageFieldView, socialIconsTemplate) {
        var LearnerProfileFieldViews = {};

        LearnerProfileFieldViews.AccountPrivacyFieldView = FieldViews.DropdownFieldView.extend({

            render: function() {
                this._super();
                this.showNotificationMessage();
                this.updateFieldValue();
                return this;
            },

            showNotificationMessage: function() {
                var accountSettingsLink = HtmlUtils.joinHtml(
                    HtmlUtils.interpolateHtml(
                        HtmlUtils.HTML('<a href="{settings_url}">'), {settings_url: this.options.accountSettingsPageUrl}
                    ),
                    gettext('Account Settings page.'),
                    HtmlUtils.HTML('</a>')
                );
                if (this.profileIsPrivate) {
                    this._super(
                        HtmlUtils.interpolateHtml(
                            gettext('You must specify your birth year before you can share your full profile. To specify your birth year, go to the {account_settings_page_link}'),  // eslint-disable-line max-len
                            {account_settings_page_link: accountSettingsLink}
                        )
                    );
                } else if (this.requiresParentalConsent) {
                    this._super(
                        HtmlUtils.interpolateHtml(
                            gettext('You must be over 13 to share a full profile. If you are over 13, make sure that you have specified a birth year on the {account_settings_page_link}'),  // eslint-disable-line max-len
                            {account_settings_page_link: accountSettingsLink}
                        )
                    );
                } else {
                    this._super('');
                }
            },

            updateFieldValue: function() {
                if (!this.isAboveMinimumAge) {
                    this.$('.u-field-value select').val('private');
                    this.disableField(true);
                }
            }
        });

        LearnerProfileFieldViews.ProfileImageFieldView = ImageFieldView.extend({

            screenReaderTitle: gettext('Profile Image'),

            imageUrl: function() {
                return this.model.profileImageUrl();
            },

            imageAltText: function() {
                return StringUtils.interpolate(
                    gettext('Profile image for {username}'),
                    {username: this.model.get('username')}
                );
            },

            imageChangeSucceeded: function() {
                var view = this;
                // Update model to get the latest urls of profile image.
                this.model.fetch().done(function() {
                    view.setCurrentStatus('');
                    view.render();
                    view.$('.u-field-upload-button').focus();
                }).fail(function() {
                    view.setCurrentStatus('');
                    view.showErrorMessage(view.errorMessage);
                });
            },

            imageChangeFailed: function(e, data) {
                this.setCurrentStatus('');
                this.showImageChangeFailedMessage(data.jqXHR.status, data.jqXHR.responseText);
            },

            showImageChangeFailedMessage: function(status, responseText) {
                var errors;
                if (_.contains([400, 404], status)) {
                    try {
                        errors = JSON.parse(responseText);
                        this.showErrorMessage(errors.user_message);
                    } catch (error) {
                        this.showErrorMessage(this.errorMessage);
                    }
                } else {
                    this.showErrorMessage(this.errorMessage);
                }
            },

            showErrorMessage: function(message) {
                this.options.messageView.showMessage(message);
            },

            isEditingAllowed: function() {
                return this.model.isAboveMinimumAge();
            },

            isShowingPlaceholder: function() {
                return !this.model.hasProfileImage();
            },

            clickedRemoveButton: function(e, data) {
                this.options.messageView.hideMessage();
                this._super(e, data);
            },

            fileSelected: function(e, data) {
                this.options.messageView.hideMessage();
                this._super(e, data);
            }
        });

        LearnerProfileFieldViews.SocialLinkIconsView = Backbone.View.extend({

            initialize: function(options) {
                this.options = _.extend({}, options);
            },

            render: function() {
                HtmlUtils.setHtml(this.$el, HtmlUtils.template(socialIconsTemplate)({
                    social_links: {
                        social_links: this.model.get('social_links'),
                        facebook: this.model.get('facebook_link'),
                        twitter: this.model.get('twitter_link'),
                        linkedin: this.model.get('linkedin_link')
                    }
                }));
                return this;
            }
        })

        return LearnerProfileFieldViews;
    });
}).call(this, define || RequireJS.define);
