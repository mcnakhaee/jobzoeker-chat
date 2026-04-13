import re                                                                                                                                                                                                                
                                                                                                                                                                                                                           
# ---------------------------------------------------------------------------                                                                                                                                            
# Caveman compression inspired by https://github.com/JuliusBrussee/caveman/tree/main                                                                                                                                                                                                
# Drops: articles, fillers, pleasantries, hedging                                                                                                                                                                        
# Keeps: technical terms exact, code blocks unchanged                                                                                                                                                                    
# ---------------------------------------------------------------------------                                                                                                                                            
                                                            
_ARTICLES     = r'\b(a|an|the)\b'
_FILLERS      = r'\b(just|really|basically|actually|simply|very|quite|rather|somewhat|essentially|literally)\b'
_PLEASANTRIES = r'\b(sure|certainly|of course|absolutely|happy to|glad to|great|awesome|excellent|wonderful|fantastic|of course)\b'
_HEDGING      = r'\b(might|perhaps|possibly|probably|it seems|it appears|i think|i believe|you may want to|you might want to|feel free to)\b'

_SYNONYM_MAP  = {
      r'\bextensive\b':           'big',
      r'\butilize\b':             'use',
      r'\bimplement a solution\b':'fix',
      r'\bleverage\b':            'use',
      r'\bfacilitate\b':          'help',
      r'\binitiate\b':            'start',
      r'\bterminate\b':           'stop',
      r'\bpurchase\b':            'buy',
      r'\bdemonstrate\b':         'show',
  }

def caveman(text: str) -> str:
      # Extract code blocks so they are never touched
      code_blocks = {}
      def stash(m):
          key = f"__CODE_{len(code_blocks)}__"
          code_blocks[key] = m.group(0)
          return key
      text = re.sub(r'```[\s\S]*?```|`[^`]+`', stash, text)

      for pattern, replacement in _SYNONYM_MAP.items():
          text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

      for pattern in [_PLEASANTRIES, _HEDGING, _FILLERS, _ARTICLES]:
          text = re.sub(pattern, '', text, flags=re.IGNORECASE)

      text = re.sub(r' {2,}', ' ', text).strip()

      # Restore code blocks
      for key, block in code_blocks.items():
          text = text.replace(key, block)

      return text


  # ---------------------------------------------------------------------------
  # Stopword removal
  # Lighter than caveman — strips function words while keeping all content words
  # ---------------------------------------------------------------------------

_STOPWORDS = {
      'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it', 'its',
      'they', 'them', 'their', 'this', 'that', 'these', 'those',
      'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
      'have', 'has', 'had', 'do', 'does', 'did',
      'will', 'would', 'could', 'should', 'shall', 'may', 'can',
      'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with', 'from',
      'and', 'or', 'but', 'so', 'if', 'as', 'than', 'then',
      'also', 'more', 'some', 'any', 'all', 'each', 'other',
      'about', 'into', 'up', 'out', 'there', 'here', 'how', 'what', 'which',
  }

def remove_stopwords(text: str) -> str:
      return ' '.join(w for w in text.split() if w.lower() not in _STOPWORDS)