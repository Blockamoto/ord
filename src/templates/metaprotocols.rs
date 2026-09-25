use super::*;

#[derive(Boilerplate)]
pub(crate) struct MetaprotocolsHtml {
  pub(crate) metaprotocols: Vec<String>,
}

impl PageContent for MetaprotocolsHtml {
  fn title(&self) -> String {
    "Metaprotocols".into()
  }
}

#[cfg(test)]
mod tests {
  use super::*;

  #[test]
  fn html() {
    assert_regex_match!(
      MetaprotocolsHtml {
        metaprotocols: vec!["Denom".into(), "denom".into()],
      },
      "
        <h1>Metaprotocols</h1>
        <ul>
          <li><a href=/metaprotocol/Denom>Denom</a></li>
          <li><a href=/metaprotocol/denom>denom</a></li>
        </ul>
      "
      .unindent()
    );
  }
}
