# Graph Metrics Verification Queries

## Gremlin Commands to Verify New Metrics

### 1. Check if Metrics Exist on Nodes

```gremlin
// Count pages with all three metrics
g.V().hasLabel('Page')
 .has('hierarchy_depth')
 .has('child_count')
 .has('graph_centrality_score')
 .count()

// Check specific page metrics
g.V('page_id_here')
 .valueMap('title', 'hierarchy_depth', 'child_count', 'graph_centrality_score')
```

### 2. Hierarchy Depth Analysis

```gremlin
// Distribution of hierarchy depths
g.V().hasLabel('Page')
 .groupCount().by('hierarchy_depth')

// Find root pages (depth = 0)
g.V().hasLabel('Page')
 .has('hierarchy_depth', 0)
 .values('title')

// Find deepest pages
g.V().hasLabel('Page')
 .order().by('hierarchy_depth', desc)
 .limit(10)
 .valueMap('title', 'hierarchy_depth')
```

### 3. Child Count Queries

```gremlin
// Pages with most children
g.V().hasLabel('Page')
 .order().by('child_count', desc)
 .limit(10)
 .valueMap('title', 'child_count')

// Average children per page
g.V().hasLabel('Page')
 .values('child_count')
 .mean()

// Pages with no children (leaf nodes)
g.V().hasLabel('Page')
 .has('child_count', 0)
 .count()
```

### 4. Centrality Score Analysis

```gremlin
// Most important pages by centrality
g.V().hasLabel('Page')
 .order().by('graph_centrality_score', desc)
 .limit(10)
 .valueMap('title', 'graph_centrality_score', 'space_key')

// Average centrality score
g.V().hasLabel('Page')
 .values('graph_centrality_score')
 .mean()

// Centrality distribution by space
g.V().hasLabel('Page')
 .group()
 .by('space_key')
 .by(values('graph_centrality_score').mean())
```

### 5. Combined Metrics Queries

```gremlin
// Find hub pages (high centrality + many children)
g.V().hasLabel('Page')
 .has('child_count', gte(5))
 .has('graph_centrality_score', gte(0.02))
 .valueMap('title', 'child_count', 'graph_centrality_score')

// Find overview pages (low depth + high importance)
g.V().hasLabel('Page')
 .has('hierarchy_depth', lte(1))
 .order().by('graph_centrality_score', desc)
 .limit(10)
 .valueMap('title', 'hierarchy_depth', 'graph_centrality_score')
```

## How These Metrics Enhance Search

### 1. **Importance-Based Ranking**
```gremlin
// Search for "monitoring" pages ranked by importance
g.V().hasLabel('Page')
 .has('content', containing('monitoring'))
 .order().by('graph_centrality_score', desc)
 .limit(10)
 .valueMap('title', 'graph_centrality_score')
```

**Benefits:**
- Returns most authoritative pages first
- Reduces noise from peripheral content
- Helps users find canonical documentation

### 2. **Hierarchical Navigation**
```gremlin
// Find section overview pages
g.V().hasLabel('Page')
 .has('hierarchy_depth', lte(1))
 .has('child_count', gte(3))
 .has('space_key', 'observability')
 .valueMap('title', 'child_count')
```

**Benefits:**
- Quick access to overview content
- Better content organization understanding
- Improved navigation experience

### 3. **Context-Aware Search**
```gremlin
// Find detailed implementation pages
g.V().hasLabel('Page')
 .has('hierarchy_depth', gte(3))
 .has('content', containing('implementation'))
 .valueMap('title', 'hierarchy_depth')

// Find intermediate tutorial pages
g.V().hasLabel('Page')
 .has('hierarchy_depth', between(1, 2))
 .has('content', containing('guide'))
 .valueMap('title', 'hierarchy_depth')
```

**Benefits:**
- Match search intent with content depth
- Distinguish overviews from details
- Provide appropriate level of information

### 4. **Hub Detection**
```gremlin
// Find knowledge centers
g.V().hasLabel('Page')
 .and(
   has('child_count', gte(5)),
   has('graph_centrality_score', gte(0.02))
 )
 .valueMap('title', 'child_count', 'graph_centrality_score')
```

**Benefits:**
- Identify comprehensive resource pages
- Find well-connected content clusters
- Discover key documentation areas

### 5. **Smart Result Filtering**
```gremlin
// Combine text search with metrics filtering
g.V().hasLabel('Page')
 .has('content', containing('troubleshooting'))
 .has('hierarchy_depth', gte(2))  // Skip high-level pages
 .has('graph_centrality_score', gte(0.005))  // Ensure some importance
 .order().by('graph_centrality_score', desc)
 .limit(10)
 .valueMap('title', 'hierarchy_depth', 'graph_centrality_score')
```

**Benefits:**
- More relevant search results
- Better match with user intent
- Reduced information overload

## Azure AI Search Integration

These metrics can be used in Azure AI Search scoring profiles:

```json
{
  "scoringProfiles": [
    {
      "name": "graph-aware-scoring",
      "functions": [
        {
          "fieldName": "graph_centrality_score",
          "interpolation": "linear",
          "type": "magnitude",
          "boost": 2.0,
          "magnitude": {
            "boostingRangeStart": 0.001,
            "boostingRangeEnd": 0.1
          }
        },
        {
          "fieldName": "hierarchy_depth",
          "interpolation": "linear",
          "type": "magnitude",
          "boost": 1.5,
          "magnitude": {
            "boostingRangeStart": 3,
            "boostingRangeEnd": 0
          }
        },
        {
          "fieldName": "child_count",
          "interpolation": "logarithmic",
          "type": "magnitude",
          "boost": 1.2,
          "magnitude": {
            "boostingRangeStart": 1,
            "boostingRangeEnd": 20
          }
        }
      ]
    }
  ]
}
```

This configuration will:
- **Boost** pages with high centrality scores (important pages)
- **Prefer** pages with lower hierarchy depth for general queries
- **Consider** pages with more children as potentially more comprehensive
- **Combine** with text relevance for optimal results