/**
 * VideoTranscriptLanguages shows list of available transcript languages.
 */
define([
    'jquery', 'backbone', 'underscore', 'gettext',
    'edx-ui-toolkit/js/utils/html-utils',
    'edx-ui-toolkit/js/utils/string-utils',
    'text!templates/transcript-languages.underscore'
],
function($, Backbone, _, gettext, HtmlUtils, StringUtils, TranscriptLanguagesViewTemplate) {
    'use strict';

    var VideoTranscriptLanguages = Backbone.View.extend({
        el: 'div.transcript-languages-wrapper',

        events: {
            'click .action-add-language': 'addLanguageMenu',
            'click .action-select-language': 'languageAdded',
            'click .action-cancel-language': 'languageCancelled',
            'click .action-remove-language': 'languageRemoved',
            'click .action-save-transcript-preferences': 'submitSelectedLanguages',
            'click .action-cancel-transcript-preferences': 'destroyView'
        },

        initialize: function(options) {
            this.selectedLanguages = [];
            this.availableLanguages = options.availableLanguages;
            this.activeLanguages = options.activeLanguages;
            this.template = HtmlUtils.template(TranscriptLanguagesViewTemplate);
            this.listenTo(Backbone, 'videotranscripts:showTranscriptLanguages', this.render);
        },

        addLanguageMenu: function() {
            var availableLanguages,
                $transcriptLanguage,
                $languagesContainer = this.$el.find('.languages-menu-container'),
                totalCurrentLanguageMenus = $languagesContainer.find('.transcript-language-menu').length;

            // Omit out selected languages from selecting again.
             availableLanguages = _.omit(this.availableLanguages, this.selectedLanguages);

            HtmlUtils.append(
                $languagesContainer,
                HtmlUtils.joinHtml(
                    HtmlUtils.HTML('<div class="transcript-language-menu-container">'),
                    HtmlUtils.interpolateHtml(
                        HtmlUtils.HTML('<select class="transcript-language-menu" id="transcript-language-menu-{languageMenuId}"></select>'),
                        {
                            languageMenuId: totalCurrentLanguageMenus
                        }
                    ),
                    HtmlUtils.HTML('<a href="#" class="action-select-language">Add</a>'),
                    HtmlUtils.HTML('<a href="#" class="action-cancel-language">Cancel</a>'),
                    HtmlUtils.HTML('</div>')
                )
            );
            $transcriptLanguage = this.$el.find('#transcript-language-menu-' + totalCurrentLanguageMenus);

            $transcriptLanguage.append(new Option('Choose a language', ''));
            _.each(availableLanguages, function(value, key){
                $transcriptLanguage.append(new Option(value, key));
            });
        },

        render: function(options) {
            HtmlUtils.setHtml(
                this.$el,
                this.template(options)
            );

            if (this.activeLanguages) {
                this.setActiveLanguages();
            } else {
                // Add a language dropdown if active languages is empty.
                this.addLanguageMenu();
            }
            return this;
        },

        setActiveLanguages: function() {
            var self = this,
                $languagesContainer = this.$el.find('.languages-menu-container');

            _.each(this.activeLanguages, function(activeLanguage){
                // Only add if not in the list already.
                if (_.indexOf(self.selectedLanguages, activeLanguage) === -1) {
                    self.selectedLanguages.push(activeLanguage);
                    HtmlUtils.append(
                        $languagesContainer,
                        HtmlUtils.joinHtml(
                            HtmlUtils.HTML('<div class="transcript-language-menu-container">'),
                            HtmlUtils.interpolateHtml(
                                HtmlUtils.HTML('<span>{languageDisplayName}</span>'),
                                {
                                    languageDisplayName: self.availableLanguages[activeLanguage]
                                }
                            ),
                            HtmlUtils.interpolateHtml(
                                HtmlUtils.HTML('<a href="#" class="action-remove-language" data-language-code="{languageCode}">Remove</a>'),
                                {
                                    languageCode: activeLanguage
                                }
                            ),
                            HtmlUtils.HTML('</div>')
                        )
                    );
                }
            });
        },

        languageAdded: function(event) {
            var $parentEl = $(event.target.parentElement),
                selectedLanguage = $parentEl.find('select').val();

            // Only add if not in the list already.
            if (selectedLanguage && _.indexOf(this.selectedLanguages, selectedLanguage) === -1) {
                this.selectedLanguages.push(selectedLanguage);
                HtmlUtils.setHtml(
                    $parentEl,
                    HtmlUtils.joinHtml(
                        HtmlUtils.interpolateHtml(
                            HtmlUtils.HTML('<span>{languageDisplayName}</span>'),
                            {
                                languageDisplayName: this.availableLanguages[selectedLanguage]
                            }
                        ),
                        HtmlUtils.interpolateHtml(
                            HtmlUtils.HTML('<a href="#" class="action-remove-language" data-language-code="{languageCode}">Remove</a>'),
                            {
                                languageCode: selectedLanguage
                            }
                        )
                    )
                )
            }
        },

        languageCancelled: function(event) {
            $(event.target.parentElement).remove();
        },

        languageRemoved: function(event) {
            var selectedLanguage = $(event.target).data('language-code');
            $(event.target.parentElement).remove();
            this.selectedLanguages.pop(selectedLanguage);
        },

        destroyView: function(event) {
            // trigger destroy transcript event.
            Backbone.trigger('videotranscripts:destroyTranscriptLanguages');

            // Unbind any events associated
            this.undelegateEvents();

            // Empty this.$el content from DOM
            this.$el.empty();

            this.selectedLanguages = [];
        },

        submitSelectedLanguages: function(event) {
            Backbone.trigger('videotranscripts:saveTranscriptPreferences', this.selectedLanguages);
            this.destroyView();
        }
    });

    return VideoTranscriptLanguages;
});
