# Content copied from https://github.com/LF-Engineering/insights-connector-git/blob/main/cmd/git/git.go#L150-L499

ActivityMap = {
	'about-fscking-timed-by':                 ['Reviewed-by'],
		'accked-by':                              ['Reviewed-by'],
		'aced-by':                                ['Reviewed-by'],
		'ack':                                    ['Reviewed-by'],
		'ack-by':                                 ['Reviewed-by'],
		'ackde-by':                               ['Reviewed-by'],
		'acked':                                  ['Reviewed-by'],
		'acked-and-reviewed':                     ['Reviewed-by'],
		'acked-and-reviewed-by':                  ['Reviewed-by'],
		'acked-and-tested-by':                    ['Reviewed-by', 'Tested-by'],
		'acked-b':                                ['Reviewed-by'],
		'acked-by':                               ['Reviewed-by'],
		'acked-by-stale-maintainer':              ['Reviewed-by'],
		'acked-by-with-comments':                 ['Reviewed-by'],
		'acked-by-without-testing':               ['Reviewed-by'],
		'acked-for-mfd-by':                       ['Reviewed-by'],
		'acked-for-now-by':                       ['Reviewed-by'],
		'acked-off-by':                           ['Reviewed-by'],
		'acked-the-net-bits-by':                  ['Reviewed-by'],
		'acked-the-tulip-bit-by':                 ['Reviewed-by'],
		'acked-with-apologies-by':                ['Reviewed-by'],
		'acked_by':                               ['Reviewed-by'],
		'ackedby':                                ['Reviewed-by'],
		'ackeded-by':                             ['Reviewed-by'],
		'acknowledged-by':                        ['Reviewed-by'],
		'acted-by':                               ['Reviewed-by'],
		'actually-written-by':                    ['Co-authored-by'],
		'additional-author':                      ['Co-authored-by'],
		'all-the-fault-of':                       ['Informed-by'],
		'also-analyzed-by':                       ['Reviewed-by'],
		'also-fixed-by':                          ['Co-authored-by'],
		'also-posted-by':                         ['Reported-by'],
		'also-reported-and-tested-by':            ['Reported-by', 'Tested-by'],
		'also-reported-by':                       ['Reported-by'],
		'also-spotted-by':                        ['Reported-by'],
		'also-suggested-by':                      ['Reviewed-by'],
		'also-written-by':                        ['Co-authored-by'],
		'analysed-by':                            ['Reviewed-by'],
		'analyzed-by':                            ['Reviewed-by'],
		'aoled-by':                               ['Reviewed-by'],
		'apology-from':                           ['Informed-by'],
		'appreciated-by':                         ['Informed-by'],
		'approved':                               ['Approved-by'],
		'approved-by':                            ['Approved-by'],
		'architected-by':                         ['Influenced-by'],
		'assisted-by':                            ['Co-authored-by'],
		'badly-reviewed-by ':                     ['Reviewed-by'],
		'based-in-part-on-patch-by':              ['Influenced-by'],
		'based-on':                               ['Influenced-by'],
		'based-on-a-patch-by':                    ['Influenced-by'],
		'based-on-code-by':                       ['Influenced-by'],
		'based-on-code-from':                     ['Influenced-by'],
		'based-on-comments-by':                   ['Influenced-by'],
		'based-on-idea-by':                       ['Influenced-by'],
		'based-on-original-patch-by':             ['Influenced-by'],
		'based-on-patch-by':                      ['Influenced-by'],
		'based-on-patch-from':                    ['Influenced-by'],
		'based-on-patches-by':                    ['Influenced-by'],
		'based-on-similar-patches-by':            ['Influenced-by'],
		'based-on-suggestion-from':               ['Influenced-by'],
		'based-on-text-by':                       ['Influenced-by'],
		'based-on-the-original-screenplay-by':    ['Influenced-by'],
		'based-on-the-true-story-by':             ['Influenced-by'],
		'based-on-work-by':                       ['Influenced-by'],
		'based-on-work-from':                     ['Influenced-by'],
		'belatedly-acked-by':                     ['Reviewed-by'],
		'bisected-and-acked-by':                  ['Reviewed-by'],
		'bisected-and-analyzed-by':               ['Reviewed-by'],
		'bisected-and-reported-by':               ['Reported-by'],
		'bisected-and-tested-by':                 ['Reported-by', 'Tested-by'],
		'bisected-by':                            ['Reviewed-by'],
		'bisected-reported-and-tested-by':        ['Reviewed-by', 'Tested-by'],
		'bitten-by-and-tested-by':                ['Reviewed-by', 'Tested-by'],
		'bitterly-acked-by':                      ['Reviewed-by'],
		'blame-taken-by':                         ['Informed-by'],
		'bonus-points-awarded-by':                ['Reviewed-by'],
		'boot-tested-by':                         ['Tested-by'],
		'brainstormed-with':                      ['Influenced-by'],
		'broken-by':                              ['Informed-by'],
		'bug-actually-spotted-by':                ['Reported-by'],
		'bug-fixed-by':                           ['Resolved-by'],
		'bug-found-by':                           ['Reported-by'],
		'bug-identified-by':                      ['Reported-by'],
		'bug-reported-by':                        ['Reported-by'],
		'bug-spotted-by':                         ['Reported-by'],
		'build-fixes-from':                       ['Resolved-by'],
		'build-tested-by':                        ['Tested-by'],
		'build-testing-by':                       ['Tested-by'],
		'catched-by-and-rightfully-ranted-at-by': ['Reported-by'],
		'caught-by':                              ['Reported-by'],
		'cause-discovered-by':                    ['Reported-by'],
		'cautiously-acked-by':                    ['Reviewed-by'],
		'celebrated-by':                          ['Reviewed-by'],
		'changelog-cribbed-from':                 ['Influenced-by'],
		'changelog-heavily-inspired-by':          ['Influenced-by'],
		'chucked-on-by':                          ['Reviewed-by'],
		'cked-by':                                ['Reviewed-by'],
		'cleaned-up-by':                          ['Co-authored-by'],
		'cleanups-from':                          ['Co-authored-by'],
		'co-author':                              ['Co-authored-by'],
		'co-authored':                            ['Co-authored-by'],
		'co-authored-by':                         ['Co-authored-by'],
		'co-debugged-by':                         ['Co-authored-by'],
		'co-developed-by':                        ['Co-authored-by'],
		'co-developed-with':                      ['Co-authored-by'],
		'committed':                              ['Committed-by'],
		'committed-by':                           ['Co-authored-by', 'Committed-by'],
		'compile-tested-by':                      ['Tested-by'],
		'compiled-by':                            ['Tested-by'],
		'compiled-tested-by':                     ['Tested-by'],
		'complained-about-by':                    ['Reported-by'],
		'conceptually-acked-by':                  ['Reviewed-by'],
		'confirmed-by':                           ['Reviewed-by'],
		'confirms-rustys-story-ends-the-same-by': ['Reviewed-by'],
		'contributors':                           ['Co-authored-by'],
		'credit':                                 ['Co-authored-by'],
		'credit-to':                              ['Co-authored-by'],
		'credits-by':                             ['Reviewed-by'],
		'csigned-off-by':                         ['Co-authored-by'],
		'cut-and-paste-bug-by':                   ['Reported-by'],
		'debuged-by':                             ['Tested-by'],
		'debugged-and-acked-by':                  ['Reviewed-by'],
		'debugged-and-analyzed-by':               ['Reviewed-by', 'Tested-by'],
		'debugged-and-tested-by':                 ['Reviewed-by', 'Tested-by'],
		'debugged-by':                            ['Tested-by'],
		'deciphered-by':                          ['Tested-by'],
		'decoded-by':                             ['Tested-by'],
		'delightedly-acked-by':                   ['Reviewed-by'],
		'demanded-by':                            ['Reported-by'],
		'derived-from-code-by':                   ['Co-authored-by'],
		'designed-by':                            ['Influenced-by'],
		'diagnoised-by':                          ['Tested-by'],
		'diagnosed-and-reported-by':              ['Reported-by'],
		'diagnosed-by':                           ['Tested-by'],
		'discovered-and-analyzed-by':             ['Reported-by'],
		'discovered-by':                          ['Reported-by'],
		'discussed-with':                         ['Co-authored-by'],
		'earlier-version-tested-by':              ['Tested-by'],
		'embarrassingly-acked-by':                ['Reviewed-by'],
		'emphatically-acked-by':                  ['Reviewed-by'],
		'encouraged-by':                          ['Influenced-by'],
		'enthusiastically-acked-by':              ['Reviewed-by'],
		'enthusiastically-supported-by':          ['Reviewed-by'],
		'evaluated-by':                           ['Tested-by'],
		'eventually-typed-in-by':                 ['Reported-by'],
		'eviewed-by':                             ['Reviewed-by'],
		'explained-by':                           ['Influenced-by'],
		'fairly-blamed-by':                       ['Reported-by'],
		'fine-by-me':                             ['Reviewed-by'],
		'finished-by':                            ['Co-authored-by'],
		'fix-creation-mandated-by':               ['Resolved-by'],
		'fix-proposed-by':                        ['Resolved-by'],
		'fix-suggested-by':                       ['Resolved-by'],
		'fixed-by':                               ['Resolved-by'],
		'fixes-from':                             ['Resolved-by'],
		'forwarded-by':                           ['Informed-by'],
		'found-by':                               ['Reported-by'],
		'found-ok-by':                            ['Tested-by'],
		'from':                                   ['Informed-by'],
		'grudgingly-acked-by':                    ['Reviewed-by'],
		'grumpily-reviewed-by':                   ['Reviewed-by'],
		'guess-its-ok-by':                        ['Reviewed-by'],
		'hella-acked-by':                         ['Reviewed-by'],
		'helped-by':                              ['Co-authored-by'],
		'helped-out-by':                          ['Co-authored-by'],
		'hinted-by':                              ['Influenced-by'],
		'historical-research-by':                 ['Co-authored-by'],
		'humbly-acked-by':                        ['Reviewed-by'],
		'i-dont-see-any-problems-with-it':        ['Reviewed-by'],
		'idea-by':                                ['Influenced-by'],
		'idea-from':                              ['Influenced-by'],
		'identified-by':                          ['Reported-by'],
		'improved-by':                            ['Influenced-by'],
		'improvements-by':                        ['Influenced-by'],
		'includes-changes-by':                    ['Influenced-by'],
		'initial-analysis-by':                    ['Co-authored-by'],
		'initial-author':                         ['Co-authored-by'],
		'initial-fix-by':                         ['Resolved-by'],
		'initial-patch-by':                       ['Co-authored-by'],
		'initial-work-by':                        ['Co-authored-by'],
		'inspired-by':                            ['Influenced-by'],
		'inspired-by-patch-from':                 ['Influenced-by'],
		'intermittently-reported-by':             ['Reported-by'],
		'investigated-by':                        ['Tested-by'],
		'lightly-tested-by':                      ['Tested-by'],
		'liked-by':                               ['Reviewed-by'],
		'list-usage-fixed-by':                    ['Resolved-by'],
		'looked-over-by':                         ['Reviewed-by'],
		'looks-good-to':                          ['Reviewed-by'],
		'looks-great-to':                         ['Reviewed-by'],
		'looks-ok-by':                            ['Reviewed-by'],
		'looks-okay-to':                          ['Reviewed-by'],
		'looks-reasonable-to':                    ['Reviewed-by'],
		'makes-sense-to':                         ['Reviewed-by'],
		'makes-sparse-happy':                     ['Reviewed-by'],
		'maybe-reported-by':                      ['Reported-by'],
		'mentored-by':                            ['Influenced-by'],
		'modified-and-reviewed-by':               ['Reviewed-by'],
		'modified-by':                            ['Co-authored-by'],
		'more-or-less-tested-by':                 ['Tested-by'],
		'most-definitely-acked-by':               ['Reviewed-by'],
		'mostly-acked-by':                        ['Reviewed-by'],
		'much-requested-by':                      ['Reported-by'],
		'nacked-by':                              ['Reviewed-by'],
		'naked-by':                               ['Reviewed-by'],
		'narrowed-down-by':                       ['Reviewed-by'],
		'niced-by':                               ['Reviewed-by'],
		'no-objection-from-me-by':                ['Reviewed-by'],
		'no-problems-with':                       ['Reviewed-by'],
		'not-nacked-by':                          ['Reviewed-by'],
		'noted-by':                               ['Reviewed-by'],
		'noticed-and-acked-by':                   ['Reviewed-by'],
		'noticed-by':                             ['Reviewed-by'],
		'okay-ished-by':                          ['Reviewed-by'],
		'oked-to-go-through-tracing-tree-by':     ['Reviewed-by'],
		'once-upon-a-time-reviewed-by':           ['Reviewed-by'],
		'original-author':                        ['Co-authored-by'],
		'original-by':                            ['Co-authored-by'],
		'original-from':                          ['Co-authored-by'],
		'original-idea-and-signed-off-by':        ['Co-authored-by'],
		'original-idea-by':                       ['Influenced-by'],
		'original-patch-acked-by':                ['Reviewed-by'],
		'original-patch-by':                      ['Co-authored-by'],
		'original-signed-off-by':                 ['Co-authored-by'],
		'original-version-by':                    ['Co-authored-by'],
		'originalauthor':                         ['Co-authored-by'],
		'originally-by':                          ['Co-authored-by'],
		'originally-from':                        ['Co-authored-by'],
		'originally-suggested-by':                ['Influenced-by'],
		'originally-written-by':                  ['Co-authored-by'],
		'origionally-authored-by':                ['Co-authored-by'],
		'origionally-signed-off-by':              ['Co-authored-by'],
		'partially-reviewed-by':                  ['Reviewed-by'],
		'partially-tested-by':                    ['Tested-by'],
		'partly-suggested-by':                    ['Co-authored-by'],
		'patch-by':                               ['Co-authored-by'],
		'patch-fixed-up-by':                      ['Resolved-by'],
		'patch-from':                             ['Co-authored-by'],
		'patch-inspired-by':                      ['Influenced-by'],
		'patch-originally-by':                    ['Co-authored-by'],
		'patch-updated-by':                       ['Co-authored-by'],
		'patiently-pointed-out-by':               ['Reported-by'],
		'pattern-pointed-out-by':                 ['Influenced-by'],
		'performance-tested-by':                  ['Tested-by'],
		'pinpointed-by':                          ['Reported-by'],
		'pointed-at-by':                          ['Reported-by'],
		'pointed-out-and-tested-by':              ['Reported-by', 'Tested-by'],
		'proposed-by':                            ['Reported-by'],
		'pushed-by':                              ['Co-authored-by'],
		'ranted-by':                              ['Reported-by'],
		're-reported-by':                         ['Reported-by'],
		'reasoning-sounds-sane-to':               ['Reviewed-by'],
		'recalls-having-tested-once-upon-a-time-by': ['Tested-by'],
		'received-from':                                  ['Informed-by'],
		'recommended-by':                                 ['Reviewed-by'],
		'reivewed-by':                                    ['Reviewed-by'],
		'reluctantly-acked-by':                           ['Reviewed-by'],
		'repored-and-bisected-by':                        ['Reported-by'],
		'reporetd-by':                                    ['Reported-by'],
		'reporeted-and-tested-by':                        ['Reported-by', 'Tested-by'],
		'report-by':                                      ['Reported-by'],
		'reportded-by':                                   ['Reported-by'],
		'reported':                                       ['Reported-by'],
		'reported--and-debugged-by':                      ['Reported-by', 'Tested-by'],
		'reported-acked-and-tested-by':                   ['Reported-by', 'Tested-by'],
		'reported-analyzed-and-tested-by':                ['Reported-by'],
		'reported-and-acked-by':                          ['Reviewed-by'],
		'reported-and-bisected-and-tested-by':            ['Reviewed-by', 'Tested-by'],
		'reported-and-bisected-by':                       ['Reported-by'],
		'reported-and-reviewed-and-tested-by':            ['Reviewed-by', 'Tested-by'],
		'reported-and-root-caused-by':                    ['Reported-by'],
		'reported-and-suggested-by':                      ['Reported-by'],
		'reported-and-test-by':                           ['Reported-by'],
		'reported-and-tested-by':                         ['Tested-by'],
		'reported-any-tested-by':                         ['Tested-by'],
		'reported-bisected-and-tested-by':                ['Reported-by', 'Tested-by'],
		'reported-bisected-and-tested-by-the-invaluable': ['Reported-by', 'Tested-by'],
		'reported-bisected-tested-by':                    ['Reported-by', 'Tested-by'],
		'reported-bistected-and-tested-by':               ['Reported-by', 'Tested-by'],
		'reported-by':                                    ['Reported-by'],
		'reported-by-and-tested-by':                      ['Reported-by', 'Tested-by'],
		'reported-by-tested-by':                          ['Tested-by'],
		'reported-by-with-patch':                         ['Reported-by'],
		'reported-debuged-tested-acked-by':               ['Tested-by'],
		'reported-off-by':                                ['Reported-by'],
		'reported-requested-and-tested-by':               ['Reported-by', 'Tested-by'],
		'reported-reviewed-and-acked-by':                 ['Reviewed-by'],
		'reported-tested-and-acked-by':                   ['Reviewed-by', 'Tested-by'],
		'reported-tested-and-bisected-by':                ['Reported-by', 'Tested-by'],
		'reported-tested-and-fixed-by':                   ['Co-authored-by', 'Reported-by', 'Tested-by'],
		'reported-tested-by':                             ['Tested-by'],
		'reported_by':                                    ['Reported-by'],
		'reportedy-and-tested-by':                        ['Reported-by', 'Tested-by'],
		'reproduced-by':                                  ['Tested-by'],
		'requested-and-acked-by':                         ['Reviewed-by'],
		'requested-and-tested-by':                        ['Tested-by'],
		'requested-by':                                   ['Reported-by'],
		'researched-with':                                ['Co-authored-by'],
		'reveiewed-by':                                   ['Reviewed-by'],
		'review-by':                                      ['Reviewed-by'],
		'reviewd-by':                                     ['Reviewed-by'],
		'reviewed':                                       ['Reviewed-by'],
		'reviewed-and-tested-by':                         ['Reviewed-by', 'Tested-by'],
		'reviewed-and-wanted-by':                         ['Reviewed-by'],
		'reviewed-by':                                    ['Reviewed-by'],
		'reviewed-off-by':                                ['Reviewed-by'],
		'reviewed–by':                                    ['Reviewed-by'],
		'reviewer':                                       ['Reviewed-by'],
		'reviewws-by':                                    ['Reviewed-by'],
		'root-cause-analysis-by':                         ['Reported-by'],
		'root-cause-found-by':                            ['Reported-by'],
		'seconded-by':                                    ['Reviewed-by'],
		'seems-ok':                                       ['Reviewed-by'],
		'seems-reasonable-to':                            ['Reviewed-by'],
		'sefltests-acked-by':                             ['Reviewed-by'],
		'sent-by':                                        ['Informed-by'],
		'serial-parts-acked-by':                          ['Reviewed-by'],
		'siged-off-by':                                   ['Co-authored-by'],
		'sighed-off-by':                                  ['Co-authored-by'],
		'signed':                                         ['Signed-off-by'],
		'signed-by':                                      ['Signed-off-by'],
		'signed-off':                                     ['Signed-off-by'],
		'signed-off-by':                                  ['Co-authored-by', 'Signed-off-by'],
		'singend-off-by':                                 ['Co-authored-by'],
		'slightly-grumpily-acked-by':                     ['Reviewed-by'],
		'smoke-tested-by':                                ['Tested-by'],
		'some-suggestions-by':                            ['Influenced-by'],
		'spotted-by':                                     ['Reported-by'],
		'submitted-by':                                   ['Co-authored-by'],
		'suggested-and-acked-by':                         ['Reviewed-by'],
		'suggested-and-reviewed-by':                      ['Reviewed-by'],
		'suggested-and-tested-by':                        ['Reviewed-by', 'Tested-by'],
		'suggested-by':                                   ['Reviewed-by'],
		'tested':                                         ['Tested-by'],
		'tested-and-acked-by':                            ['Tested-by'],
		'tested-and-bugfixed-by':                         ['Resolved-by', 'Tested-by'],
		'tested-and-reported-by':                         ['Reported-by', 'Tested-by'],
		'tested-by':                                      ['Tested-by'],
		'tested-off':                                     ['Tested-by'],
		'thanks-to':                                      ['Influenced-by', 'Informed-by'],
		'to':                                             ['Informed-by'],
		'tracked-by':                                     ['Tested-by'],
		'tracked-down-by':                                ['Tested-by'],
		'was-acked-by':                                   ['Reviewed-by'],
		'weak-reviewed-by':                               ['Reviewed-by'],
		'workflow-found-ok-by':                           ['Reviewed-by'],
		'written-by':                                     ['Reported-by']
}
