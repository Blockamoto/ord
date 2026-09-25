use super::*;

#[derive(Boilerplate)]
pub(crate) struct MetaprotocolHtml {
  pub(crate) metaprotocol: String,
  pub(crate) inscriptions: Vec<InscriptionId>,
  pub(crate) prev: Option<u32>,
  pub(crate) next: Option<u32>,
}

impl PageContent for MetaprotocolHtml {
  fn title(&self) -> String {
    format!("Metaprotocol {}", self.metaprotocol)
  }
}

#[cfg(test)]
mod tests {
  use super::*;

  #[test]
  fn without_prev_and_next() {
    assert_regex_match!(
      MetaprotocolHtml {
        metaprotocol: "denom".into(),
        inscriptions: vec![inscription_id(1), inscription_id(2)],
        prev: None,
        next: None,
      },
      "
        <h1>Metaprotocol denom</h1>
        <div class=thumbnails>
          <a href=/inscription/1{64}i1><iframe .* src=/preview/1{64}i1></iframe></a>
          <a href=/inscription/2{64}i2><iframe .* src=/preview/2{64}i2></iframe></a>
        </div>
        .*
        prev
        next
        .*
      "
      .unindent()
    );
  }

  #[test]
  fn with_prev_and_next() {
    assert_regex_match!(
      MetaprotocolHtml {
        metaprotocol: "denom".into(),
        inscriptions: vec![inscription_id(1), inscription_id(2)],
        prev: Some(1),
        next: Some(2),
      },
      "
        <h1>Metaprotocol denom</h1>
        <div class=thumbnails>
          <a href=/inscription/1{64}i1><iframe .* src=/preview/1{64}i1></iframe></a>
          <a href=/inscription/2{64}i2><iframe .* src=/preview/2{64}i2></iframe></a>
        </div>
        .*
        <a class=prev href=/metaprotocol/denom/1>prev</a>
        <a class=next href=/metaprotocol/denom/2>next</a>
        .*
      "
      .unindent()
    );
  }
}
